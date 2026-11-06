"""Initialize local secrets and optionally synchronize the Docker PostgreSQL role.

The generated values are never printed. Existing non-placeholder values are
preserved. On first use, backend/.env is copied from backend/.env.example.
This helper is intended for local development only.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"
ENV_EXAMPLE_FILE = BACKEND_DIR / ".env.example"
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
        # Keep duplicate dotenv entries consistent. Compose and python-dotenv
        # otherwise let a later blank entry override the generated value.
        return pattern.sub(replacement, contents)
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


def _synchronize_postgres_password(*, database_user: str, password: str) -> None:
    if not IDENTIFIER_PATTERN.fullmatch(database_user):
        raise ValueError("POSTGRES_USER must be a valid PostgreSQL identifier.")

    sql = (
        f'ALTER ROLE "{database_user}" WITH PASSWORD '
        f"{_quote_sql_literal(password)};\n"
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
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
    parser.add_argument(
        "--sync-postgres",
        action="store_true",
        help="also update the password in an already-running Compose database",
    )
    args = parser.parse_args()

    if not ENV_FILE.is_file():
        if not ENV_EXAMPLE_FILE.is_file():
            raise FileNotFoundError(
                f"Environment template not found: {ENV_EXAMPLE_FILE}"
            )
        shutil.copyfile(ENV_EXAMPLE_FILE, ENV_FILE)
        env_status = "created from backend/.env.example"
    else:
        env_status = "preserved"

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
    _write_atomically(ENV_FILE, contents)

    if args.sync_postgres:
        _synchronize_postgres_password(
            database_user=database_user,
            password=postgres_password,
        )

    print(f"backend/.env: {env_status}")
    print(f"SECRET_KEY: {secret_status} (value hidden)")
    print(f"POSTGRES_PASSWORD: {password_status} (value hidden)")
    if args.sync_postgres:
        print(f"PostgreSQL role '{database_user}' synchronized successfully.")
    else:
        print("PostgreSQL synchronization: skipped (normal for first setup)")


if __name__ == "__main__":
    main()
