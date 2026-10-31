# LoveWorld backend

This directory contains the initial FastAPI backend foundation. It includes a
health endpoint, environment-based settings, SQLAlchemy database plumbing, and
Alembic configuration, the initial database schema, and private bearer-token
authentication for the two provisioned accounts. The Memory API provides
authenticated, ownership-aware memory CRUD; other private data endpoints are
not implemented.

## Set up the development environment

From the repository root, enter `backend` and run these commands in PowerShell:

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.template .env
notepad .env
```

Edit `backend\.env` and replace the example password with the password for
your local PostgreSQL role. Do not commit `.env`; it is ignored by Git. If the
password contains URL-reserved characters, URL-encode them in the connection
URL. The template contains placeholders only. Set `APP_ENVIRONMENT` to
`development`, configure `JWT_SECRET` to a generated local secret, leave
`JWT_ALGORITHM` as `HS256`, and set the desired
`ACCESS_TOKEN_EXPIRE_MINUTES` (default 30).

Generate a secret directly into the Windows clipboard without displaying it:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))" | Set-Clipboard
```

Paste the generated value into `JWT_SECRET` in your ignored `.env`; do not
commit it. The
development fallback secret exists only so local health checks and tests can
start without extra setup. Production requires `APP_ENVIRONMENT=production`
and an explicitly configured JWT secret of at least 32 characters that is not
a development placeholder.

## Configure PostgreSQL

Install and start PostgreSQL locally, then create a role and database and
ensure the role in `DATABASE_URL` can connect to it. Connect from PowerShell:

```powershell
psql -U postgres -h localhost -p 6666
```

Then run these statements at the `psql` prompt, replacing the placeholder
password with a local password:

```sql
CREATE ROLE loveworld_user WITH LOGIN PASSWORD 'replace-with-a-local-password';
CREATE DATABASE loveworld;
GRANT ALL PRIVILEGES ON DATABASE loveworld TO loveworld_user;
```

Set `DATABASE_URL` in `.env` to the corresponding local connection string,
using the psycopg driver:

```text
DATABASE_URL=postgresql+psycopg://loveworld_user:replace-me@localhost:6666/loveworld
```

The application does not connect to PostgreSQL when imported. A database
connection is opened only when a request uses the database session dependency,
the database connectivity check is requested, or Alembic runs an online
migration.

## Run tests and the backend

From the `backend` directory, with the virtual environment activated:

```powershell
python -m pytest
python -m uvicorn app.main:app --reload
```

The health endpoint is available at <http://127.0.0.1:8000/health>. Interactive
API documentation is available at <http://127.0.0.1:8000/docs>.

## Check database connectivity

`GET /health` checks that the API is running and does not depend on PostgreSQL.
`GET /health/db` separately runs `SELECT 1`: it returns `{"status":"ok"}` when
the database is reachable, or a generic `503` response when it is unavailable.
It does not return database URLs or exception details.

With the server running, check PostgreSQL reachability from PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/db
```

## Database migrations

Alembic reads the same `DATABASE_URL` setting as the application. Online
migrations require `DATABASE_URL` to be explicitly set in the environment or
`backend\.env`; the local fallback URL is not sufficient. Offline SQL
generation does not connect to a database.

The initial schema migration creates the five model tables. Revision
`ff850c33e28e` adds private-by-default visibility to memories, notes, and
photos. To review migration status from the `backend` directory:

```powershell
python -m alembic current
Get-ChildItem .\alembic\versions\*.py | ForEach-Object { Get-Content $_.FullName }
python -m alembic upgrade head
```

Do not run `upgrade head` until you have reviewed pending migrations and
confirmed that they target the intended database. Future model modules must
be imported from `app/db/models.py` so their tables are registered for
autogenerate.

## Authentication

Passwords are hashed with Argon2id before they are stored. Authentication
uses short-lived HS256 JWT bearer tokens signed with `JWT_SECRET`. Tokens
contain the user ID as `sub`, plus issued-at, expiry, and a unique token ID.
The default expiration is 30 minutes and can be changed with
`ACCESS_TOKEN_EXPIRE_MINUTES` (1–1440 minutes). There are no refresh tokens.

The login endpoint accepts JSON and never creates accounts. This PowerShell
example prompts for the password without echoing it or placing it in command
history:

```powershell
$username = Read-Host "Username"
$securePassword = Read-Host "Password" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $body = @{ username = $username; password = $password } | ConvertTo-Json
    $token = (Invoke-RestMethod -Method Post `
      -Uri http://127.0.0.1:8000/auth/login `
      -ContentType "application/json" -Body $body).access_token
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    Remove-Variable password, body, securePassword -ErrorAction SilentlyContinue
}
```

Avoid putting real passwords in shared scripts or source control. To fetch the
safe current-user profile:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/auth/me `
  -Headers @{ Authorization = "Bearer $token" }
```

Provision the two intended accounts separately from normal server startup.
From `backend`, run `python -m app.cli provision-user`; enter each username
and display name when prompted, then enter and confirm the password at the
hidden prompts. Passwords must be 12–128 characters. The command hashes the
password, rejects duplicate usernames, and refuses to create more than two
users. It does not print passwords or hashes. Never provision real accounts
in automated tests or commit their credentials.

JWT authentication confirms identity and active account status. It does not
by itself authorize access to private resources. The Memory API applies
resource-level ownership and visibility checks; other resource endpoints must
add their own authorization when implemented.

## Resource ownership and privacy

Memory, love-note, and photo rows each retain their existing owner foreign key
(`created_by` or `uploaded_by`). A new `visibility` field distinguishes
`private` from `shared`, defaults to `private`, and is constrained to those
values. Existing rows are migrated as private. The reusable authorization
helpers allow the owner to access their item; an explicitly shared item may be
read by either authenticated user. Only the owner may mutate an item. Missing
or inaccessible items return the same `404` response to avoid confirming that
another user's private item exists. Resource creation must assign ownership
from the authenticated user, not client-supplied JSON.

Memory, LoveNote, and Photo metadata CRUD are described below. Image uploads
and storage are not implemented. Authentication identifies the requesting
user; ownership checks provide authorization and are applied by each resource
endpoint.

## Memory API

The Memory API stores memory metadata and requires an active user's bearer
token on every endpoint. Creation always assigns `created_by` from the token's
authenticated user; `created_by` is not accepted in request bodies. New
memories are private unless the owner explicitly requests `visibility:
"shared"`. The owner may read, update, and delete their memory. Another user
may read a shared memory, but cannot update or delete it. Missing and
inaccessible memory IDs return the same generic 404 response.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/memories` | Create a memory owned by the authenticated user |
| GET | `/memories` | List owned memories and explicitly shared memories |
| GET | `/memories/{memory_id}` | Retrieve an accessible memory |
| PATCH | `/memories/{memory_id}` | Update an owned memory |
| DELETE | `/memories/{memory_id}` | Delete an owned memory |

Example create request:

```json
{
  "title": "Our first trip",
  "description": "A favorite day together",
  "memory_date": "2026-10-31",
  "visibility": "private"
}
```

Example create response:

```json
{
  "id": 7,
  "title": "Our first trip",
  "description": "A favorite day together",
  "memory_date": "2026-10-31",
  "visibility": "private",
  "created_by": 2,
  "created_at": "2026-10-31T12:00:00Z",
  "updated_at": "2026-10-31T12:00:00Z"
}
```

`title` is required and cannot be blank; `description` is optional and limited
to 5,000 characters; `memory_date` is an optional calendar date; visibility is
`private` or `shared`. Unknown request fields are rejected, including attempts
to supply an owner ID. PATCH changes only fields supplied in its body; an empty
PATCH is rejected with `422`. `description` and `memory_date` may be set to
`null` to clear them.

The list endpoint accepts `limit` (1–100, default 20) and `offset` (0 or
greater, default 0). Results are ordered newest first, with ID as a stable
tie-breaker, and include `items`, `total`, `limit`, and `offset`. Responses
include memory fields and timestamps, but no user credentials or internal
database objects.

Common status codes are `201` for creation, `200` for reads/updates, `204` for
deletion, `401` for missing or invalid authentication, `404` for missing or
inaccessible resources, `422` for invalid input, and a generic `503` if a
database operation fails.

Run all isolated tests from `backend` with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## LoveNote API

The LoveNote API stores text notes and requires an active user's bearer token
on every endpoint. Creation assigns `created_by` from the authenticated user;
ownership fields are not accepted in request bodies. Notes default to private.
Owners can read, update, and delete their notes. Another authenticated user
can read a note only when its visibility is `shared`; sharing never grants
permission to update or delete it. Missing and inaccessible note IDs return
the same generic `404` response.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/love-notes` | Create a note owned by the authenticated user |
| GET | `/love-notes` | List owned notes and explicitly shared notes |
| GET | `/love-notes/{note_id}` | Retrieve an accessible note |
| PATCH | `/love-notes/{note_id}` | Update an owned note |
| DELETE | `/love-notes/{note_id}` | Delete an owned note |

Example create request:

```json
{
  "title": "A little reminder",
  "content": "I love you, always.",
  "visibility": "private"
}
```

Example create response:

```json
{
  "id": 7,
  "title": "A little reminder",
  "content": "I love you, always.",
  "visibility": "private",
  "created_by": 2,
  "created_at": "2026-10-31T12:00:00Z",
  "updated_at": "2026-10-31T12:00:00Z"
}
```

`content` is required, cannot be blank, and is limited to 10,000 characters.
`title` is optional, cannot be blank when supplied, and is limited to 200
characters. Visibility accepts only `private` or `shared`. Unknown request
fields are rejected. PATCH changes only supplied fields; an empty PATCH is
rejected with `422`. A note's optional title may be cleared with `null`, but
content and visibility cannot be set to `null`.

The list endpoint accepts `limit` (1–100, default 20) and `offset` (0 or
greater, default 0). Results are ordered newest first, with ID as a stable
tie-breaker, and include `items`, `total`, `limit`, and `offset`. Common status
codes are `201` for creation, `200` for reads/updates, `204` for deletion,
`401` for missing or invalid authentication, `404` for missing or inaccessible
notes, `422` for invalid input, and a generic `503` if a database operation
fails.

Run all isolated tests from `backend` with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

While the server is running, inspect request and response schemas in Swagger
at <http://127.0.0.1:8000/docs>. Photo upload/storage and authorization for
daily surprises remain unimplemented.

## Photo Metadata API

The Photo API manages metadata only and requires an active user's bearer token
on every endpoint. Creation assigns the photo owner from the authenticated
user; `uploaded_by`, `created_by`, `owner_id`, and `storage_key` are not
accepted in request bodies. New photos are private by default. Owners can
read, update, and delete their photo metadata. Another authenticated user can
read a photo only when its visibility is `shared`; sharing does not grant
permission to update or delete it. Missing and inaccessible photo IDs return
the same generic `404` response.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/photos` | Create photo metadata for the authenticated user |
| GET | `/photos` | List owned photos and explicitly shared photos |
| GET | `/photos/{photo_id}` | Retrieve accessible photo metadata |
| PATCH | `/photos/{photo_id}` | Update owned photo metadata |
| DELETE | `/photos/{photo_id}` | Delete owned photo metadata |

Example create request:

```json
{
  "original_filename": "our-day.jpg",
  "caption": "A favorite moment",
  "visibility": "private"
}
```

Example response:

```json
{
  "id": 7,
  "original_filename": "our-day.jpg",
  "caption": "A favorite moment",
  "visibility": "private",
  "uploaded_by": 2,
  "created_at": "2026-10-31T12:00:00Z"
}
```

The internal `storage_key` is generated by the server and is not included in
responses. `original_filename` is required, cannot be blank, and is limited to
255 characters. `caption` is optional, cannot be blank when supplied, and is
limited to 5,000 characters; it can be cleared with `null` in PATCH. Visibility
accepts only `private` or `shared`. Unknown fields are rejected. PATCH changes
only supplied fields and an empty PATCH is rejected with `422`.

The list endpoint accepts `limit` (1–100, default 20) and `offset` (0 or
greater, default 0). Results are ordered newest first, with ID as a stable
tie-breaker, and include `items`, `total`, `limit`, and `offset`. Common status
codes are `201` for creation, `200` for reads/updates, `204` for deletion,
`401` for missing or invalid authentication, `404` for missing or inaccessible
photos, `422` for invalid input, and a generic `503` if a database operation
fails.

These endpoints do not upload, serve, or delete image files. Deleting a photo
removes only its metadata record; physical file storage and cleanup belong to
the separate upload/storage milestone. Explore request and response schemas
in Swagger at <http://127.0.0.1:8000/docs>.

### Photo uploads and private storage

`POST /photos/upload` accepts one multipart image file in the `file` field,
plus optional `caption` and `visibility` form fields. It requires an active
user bearer token. The owner is taken from that user, and visibility defaults
to `private`. The original filename is retained only as display metadata; the
server creates an opaque storage identifier. Neither storage identifiers nor
filesystem paths are returned to clients.

Supported inputs are static JPEG, PNG, and WebP images. The server validates
the decoded image content rather than trusting its filename or declared MIME
type. GIF, SVG, animated images, corrupt or truncated files, and images above
8,000 pixels on either dimension or 40 million total pixels are rejected.
Uploads are limited to 10 MiB by default. Set `PHOTO_MAX_UPLOAD_BYTES` to a
positive integer up to 100 MiB to change the limit. Image orientation is
applied and newly encoded files omit EXIF metadata; a WebP thumbnail no larger
than 512 by 512 pixels is generated.

`PHOTO_STORAGE_DIR` configures the private local storage directory. Its
development default is `backend\var\photo-storage`, outside frontend public
directories. The directory is not mounted as static content; access is
available only through authenticated API endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/photos/upload` | Validate and store an image and thumbnail |
| GET | `/photos/{photo_id}/image` | Retrieve the authorized original |
| GET | `/photos/{photo_id}/thumbnail` | Retrieve the authorized thumbnail |

Image and thumbnail requests use the same private/shared access checks as
photo metadata. Owners can access private photos; other authenticated users
can access shared photos only. Responses use server-determined image media
types, `Cache-Control: private, no-store`, and `X-Content-Type-Options:
nosniff`.

The upload sequence writes the image files before committing metadata. If
the database write fails, the server attempts to remove both files and logs
a safe diagnostic if cleanup fails. These filesystem and database operations
are not atomic. Deletion commits metadata removal first, then removes the
original and thumbnail; if cleanup fails, the endpoint returns `503` and logs
that physical cleanup may be incomplete. Missing files during deletion are
safe to ignore. Metadata created through the metadata-only `POST /photos`
endpoint has no image files and image retrieval for it returns `404`.

Local filesystem storage is intended for development or single-instance
deployments. Production deployments must configure durable private storage
outside any web-served directory, ensure the storage is available to every
application instance, and back it up alongside the database. Restoring database
metadata without matching files (or files without metadata) can leave
unavailable or orphaned images. Object storage can replace the local
implementation behind the storage interface in a later deployment milestone;
do not expose a public bucket or permanent public URLs for private images.
