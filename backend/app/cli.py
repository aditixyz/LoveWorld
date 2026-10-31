import argparse
from getpass import getpass

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.session import SessionLocal
from app.services.users import create_user


def main() -> None:
    parser = argparse.ArgumentParser(description="LoveWorld account administration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "provision-user",
        help="interactively create one of the two private accounts",
    )
    args = parser.parse_args()

    if args.command == "provision-user":
        _provision_user()


def _provision_user() -> None:
    username = input("Username: ")
    display_name = input("Display name: ")
    password = getpass("Password (input hidden): ")
    confirmation = getpass("Confirm password (input hidden): ")
    if password != confirmation:
        raise SystemExit("Passwords did not match; no account was created.")

    try:
        with SessionLocal() as db:
            create_user(db, username, display_name, password)
            db.commit()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    except IntegrityError:
        raise SystemExit("Account could not be created; check for a duplicate username.") from None
    except SQLAlchemyError:
        raise SystemExit("Database operation failed; no account was created.") from None

    print("Account created.")


if __name__ == "__main__":
    main()
