"""Generate local secrets without reading or modifying the project's .env file."""

import secrets


def main() -> None:
    print(f"SECRET_KEY={secrets.token_urlsafe(64)}")
    print(f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}")


if __name__ == "__main__":
    main()
