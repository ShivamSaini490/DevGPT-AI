"""Initialize local secrets and synchronize the Docker PostgreSQL role safely.

The generated values are never printed. Existing non-placeholder values are
preserved. This helper is intended for local development only.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"
PLACEHOLDER_MARKERS = ("replace-with", "your ", "test-")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_env(contents: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _replace_env_value(contents: str, name: str, value: str) -> str:
    replacement = f"{name}={value}"
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=.*$", re.MULTILINE)
    if pattern.search(contents):
        return pattern.sub(replacement, contents, count=1)
    separator = "" if contents.endswith(("\n", "\r")) else os.linesep
    return f"{contents}{separator}{replacement}{os.linesep}"


def _write_atomically(path: Path, contents: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        delete=False,
    ) as temporary_file:
        temporary_file.write(contents)
        temporary_path = Path(temporary_file.name)
    os.replace(temporary_path, path)


def _quote_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _synchronize_postgres_password(
    *, container: str, database_user: str, password: str
) -> None:
    if not IDENTIFIER_PATTERN.fullmatch(database_user):
        raise ValueError("POSTGRES_USER must be a valid PostgreSQL identifier.")

    sql = (
        f'ALTER ROLE "{database_user}" WITH PASSWORD '
        f"{_quote_sql_literal(password)};\n"
    )
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "-u",
            "postgres",
            container,
            "psql",
            "-U",
            database_user,
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        error = result.stderr.strip() or "PostgreSQL password synchronization failed."
        raise RuntimeError(error)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres-container", default="devgpt-postgres")
    args = parser.parse_args()

    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"Environment file not found: {ENV_FILE}")

    contents = ENV_FILE.read_text(encoding="utf-8")
    values = _parse_env(contents)

    secret_key = values.get("SECRET_KEY")
    if _is_placeholder(secret_key):
        secret_key = secrets.token_urlsafe(64)
        contents = _replace_env_value(contents, "SECRET_KEY", secret_key)
        secret_status = "generated"
    else:
        secret_status = "preserved"

    postgres_password = values.get("POSTGRES_PASSWORD")
    if _is_placeholder(postgres_password):
        postgres_password = secrets.token_urlsafe(32)
        contents = _replace_env_value(
            contents, "POSTGRES_PASSWORD", postgres_password
        )
        password_status = "generated"
    else:
        password_status = "preserved"

    database_user = values.get("POSTGRES_USER", "devgpt")
    _synchronize_postgres_password(
        container=args.postgres_container,
        database_user=database_user,
        password=postgres_password,
    )
    _write_atomically(ENV_FILE, contents)

    print(f"SECRET_KEY: {secret_status} (value hidden)")
    print(f"POSTGRES_PASSWORD: {password_status} (value hidden)")
    print(f"PostgreSQL role '{database_user}' synchronized successfully.")


if __name__ == "__main__":
    main()
