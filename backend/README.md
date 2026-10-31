# LoveWorld backend

Private FastAPI backend for two intended users. It provides bearer-token
authentication, private/shared memory, love-note and photo metadata APIs,
private photo uploads and delivery, health checks, and Alembic-managed
PostgreSQL schema migrations.

## Development setup

From the repository root, prepare the backend environment in PowerShell:

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.template .env
```

Configure `backend\.env` locally. Set `DATABASE_URL` to a PostgreSQL connection
URL, `APP_ENVIRONMENT=development`, and `JWT_SECRET` to a unique random value.
Do not commit `.env` or paste credentials into shared logs or scripts. In
production, the application requires an explicitly configured JWT secret of
at least 32 characters that is not a development placeholder.

Settings can also be supplied through environment variables. Relevant
configuration includes:

| Variable | Default | Limits / purpose |
| --- | --- | --- |
| `DATABASE_URL` | Local PostgreSQL URL | SQLAlchemy PostgreSQL connection |
| `APP_ENVIRONMENT` | `development` | `development`, `test`, or `production` |
| `JWT_SECRET` | Development-only fallback | Production must set a strong secret |
| `JWT_ALGORITHM` | `HS256` | The supported signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | 1–1,440 minutes |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | `5` | 1–100 per username/window |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `900` | 1–86,400 seconds |
| `PHOTO_MAX_UPLOAD_BYTES` | `10485760` | 1 byte–100 MiB per image |
| `PHOTO_STORAGE_DIR` | `var/photo-storage` | Private local photo storage |

The database engine is configured for PostgreSQL through `psycopg`. Importing
the application does not itself open a database connection. Database-backed
requests, `/health/db`, and online Alembic commands do connect.

## Authentication and account provisioning

Passwords are hashed with Argon2id. `POST /auth/login` accepts a username and
password and returns a short-lived HS256 bearer token. Tokens include a user
subject, issued-at and expiry times, and a unique token ID. `GET /auth/me`
returns the authenticated user's safe profile. Protected routes require a
valid token for an active account; account creation is not exposed as an API.

Provision accounts interactively from the backend directory:

```powershell
python -m app.cli provision-user
```

The CLI normalizes usernames, enforces password length, rejects duplicate
usernames, and provisions into one of two unique account slots. Database
constraints enforce the maximum even with concurrent provisioning or direct
database inserts. Existing account IDs, usernames, and password hashes are
preserved when the slot migration is applied. The migration fails rather than
discarding rows if more than two accounts already exist.

Login attempts default to five per normalized username in a 15-minute
fixed window. PostgreSQL stores counters by HMAC digest of the username, not
as plaintext usernames. Counters are shared across application processes and
instances using the same database and JWT secret. A successful login resets
that username's counter; expired counters are removed during later login
attempts. Exceeding the limit returns a generic `429`; rate-limit database
failures fail closed with a generic `503`. The limiter is per username, not
per IP or a global request limit.

## Resource privacy

Memories, love notes and photos default to `private`. Owners can read and
mutate their own resources. The other authenticated account can read a
resource only when its owner explicitly marks it `shared`; sharing does not
grant mutation or deletion rights. Missing and inaccessible resources use
the same generic `404`. The API assigns ownership from the authenticated
account and rejects client-supplied ownership fields.

List endpoints support `limit` (1–100, default 20) and `offset` (0 or greater,
default 0), return a total count, and use deterministic newest-first ordering.
Memories, love notes, and photo metadata expose create, list, detail, update,
and delete routes under `/memories`, `/love-notes`, and `/photos`. Photo
metadata can be created without an image; image retrieval then returns `404`.

## Memories timeline

`GET /timeline` requires an active user's bearer token and combines the
authenticated user's memories and photos with resources explicitly marked
`shared` by the other account. Private resources owned by the other account
are excluded by the database queries.

The response contains `items`, `total`, `limit`, and `offset`. Each item has
`type` (`memory` or `photo`), `id`, `timeline_date`, and `visibility`, plus
metadata for that resource type. A memory uses `memory_date` when present
(represented as midnight UTC); otherwise it uses `created_at`. Photos use
`created_at`. Items are ordered by effective timeline date newest first; ties
are ordered by type (`memory` before `photo`) and then descending resource ID.
Pagination applies to the combined feed, not to each resource type separately.
Storage keys and paths are never included.

## Daily surprises

`GET /surprises/today` requires a valid bearer token for an active account.
It returns a deterministic surprise drawn from that user's accessible
memories, photos, and love notes. The selection ranks eligible resources by
type and ID, then uses a SHA-256-derived value from the authenticated user ID
and current UTC date to choose one rank. The same user receives the same
resource for a given date while the eligible collection remains unchanged;
adding or deleting content can change that day's selection.

The response contains the UTC `display_date` and either a `surprise` object
with its type, existing `resource_id`, title, a preview of up to 280
characters, and creation timestamp, or `surprise: null` when no eligible
content exists. For example:

```json
{
  "display_date": "2026-10-31",
  "surprise": {
    "type": "memory",
    "resource_id": 12,
    "title": "Our first trip",
    "preview": "A weekend by the sea...",
    "created_at": "2026-10-20T14:30:00Z"
  }
}
```

Only resources owned by the caller or explicitly marked `shared` are eligible;
another user's private content is filtered out in the database query. The API
returns display metadata only and never includes photo storage keys or paths,
password hashes, or tokens. This endpoint is stateless and reads current
resource rows, so deleted resources cannot remain as stale surprise references.
Selection is UTC-based, may repeat resources on consecutive days, and is not
guaranteed to show every item before repeating. The existing
`/daily_surprises` table is not used by this endpoint; delivery scheduling,
automatic collages, and slideshows are not implemented.

## Photo upload and storage

`POST /photos/upload` accepts a multipart `file` plus optional `caption` and
`visibility`. Only JPEG, PNG and WebP static images are accepted. The server
validates decoded image data rather than trusting MIME or filename, rejects
animated or invalid files, and limits dimensions to 8,000 pixels per side and
40 million pixels total. It applies EXIF orientation, re-encodes without EXIF
metadata, and generates a WebP thumbnail no larger than 512 by 512 pixels.

An ASGI middleware rejects upload requests before multipart parsing when
`Content-Length` exceeds the image limit plus 64 KiB. It also counts received
bytes for streamed requests without that header. The image bytes are separately
checked against `PHOTO_MAX_UPLOAD_BYTES`. Set the reverse proxy/ingress request
body limit to at least that configured image size plus 64 KiB (10 MiB plus
64 KiB by default). Proxy-side enforcement is necessary because a proxy may
buffer or reject the request before it reaches the application.

Original images and thumbnails are stored outside public frontend directories
under the configured private storage directory. `GET /photos/{id}/image` and
`GET /photos/{id}/thumbnail` require authentication and apply the same
owner/shared access checks as metadata. Responses use server-determined image
types, private no-store caching, and `nosniff`.

Filesystem storage is intended for development or a single-instance
deployment. Production needs durable private storage accessible to every
application instance and backups coordinated with the database. Database and
filesystem writes are not atomic: cleanup is attempted after failures, but
orphaned or missing files can require operational repair. Do not serve private
photos from a public bucket or permanent public URLs.

## Database migrations

The checked-in Alembic chain, in order, is:

1. `569ee1863153` — initial schema.
2. `ff850c33e28e` — private/shared visibility constraints.
3. `4f2c8a9d1b73` — database-enforced two-account slots.
4. `91d5f3a7c2e6` — shared PostgreSQL login rate-limit table.

The last two revisions are pending until applied to a database. The live
database's current revision has not been verified by this repository audit.
Before any online migration, confirm that `DATABASE_URL` targets the intended
database and review the SQL. Never point development or tests at a production
database.

Check status and apply reviewed migrations from the backend directory:

```powershell
python -m alembic current
python -m alembic heads
python -m alembic upgrade head
```

Offline SQL generation does not connect to a database:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/loveworld"
python -m alembic upgrade head --sql
Remove-Item Env:DATABASE_URL
```

Use a local throwaway database and never put actual credentials in shell
history or shared logs.

## Tests and PostgreSQL migration verification

Most automated tests use isolated in-memory SQLite databases. They verify
application behavior, not PostgreSQL migration execution. Run the complete
suite from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The opt-in PostgreSQL migration test creates a uniquely named temporary
schema, runs the complete Alembic chain inside it, compares the migrated
schema to SQLAlchemy metadata, and checks the account-slot constraints and
login rate-limit table. It then drops only that temporary schema. The test
refuses any database whose name is not exactly `loveworld_test` or prefixed
with `loveworld_test_`.

Create a dedicated, disposable PostgreSQL test database first. Set the
connection URL via the `LOVEWORLD_TEST_DATABASE_URL` environment variable in
your local shell or CI secret store; do not use `DATABASE_URL` for this test:

```powershell
$env:LOVEWORLD_TEST_DATABASE_URL = "postgresql+psycopg://test_user:password@localhost:5432/loveworld_test"
.\.venv\Scripts\python.exe -m pytest -q tests\test_postgres_migrations.py
Remove-Item Env:LOVEWORLD_TEST_DATABASE_URL
```

This integration test requires PostgreSQL connectivity and permission to
create/drop schemas in that dedicated test database. Without the variable it
is skipped. PostgreSQL migration behavior must not be inferred from SQLite
tests.

## Errors, health and deployment

`GET /health` checks application responsiveness; `GET /health/db` checks
database connectivity. Database-backed API failures return generic responses.
Server logs record a fixed operation label and exception class, not exception
text, SQL, query parameters, credentials, request bodies, passwords, or tokens.

Run the API locally with:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Interactive API documentation is available at `/docs` in development.
Production deployment must use a strong JWT secret, reviewed migrations,
private durable photo storage, reverse-proxy upload limits, TLS, backups and
appropriate access controls. The database-backed login limiter shares state
only among instances using the same database and JWT secret; it is not an
IP-based defense against distributed request flooding.
