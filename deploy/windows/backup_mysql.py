"""Run a complete mysqldump using the active ARION database configuration."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "arion_geo"))


def _option(value: object) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    return f'"{escaped}"'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mysqldump", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--temp-dir", required=True)
    args = parser.parse_args()

    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["ARION_ENV"] = "production"
    try:
        import django
        django.setup()
        from django.conf import settings
        database = settings.DATABASES["default"]
    except Exception as exc:
        print(f"Backup refused: production database configuration is unavailable ({type(exc).__name__}).")
        return 2

    if database.get("ENGINE") != "django.db.backends.mysql":
        print("Backup refused: the active production database is not MySQL.")
        return 2

    output = Path(args.output).resolve()
    temp_dir = Path(args.temp_dir).resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    if not temp_dir.is_dir() or not output.parent.is_dir():
        print("Backup refused: destination or protected temporary directory is unavailable.")
        return 2

    defaults_path = None
    partial_path = output.with_suffix(output.suffix + ".partial")
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=temp_dir,
                                         prefix="arion-mysql-", suffix=".cnf", delete=False) as config:
            defaults_path = Path(config.name)
            config.write("[client]\n")
            for key, value in (("user", database.get("USER", "")),
                               ("password", database.get("PASSWORD", "")),
                               ("host", database.get("HOST", "127.0.0.1")),
                               ("port", database.get("PORT", 3306)),
                               ("default-character-set", "utf8mb4")):
                config.write(f"{key}={_option(value)}\n")

        command = [
            args.mysqldump,
            f"--defaults-extra-file={defaults_path}",
            "--single-transaction", "--quick", "--routines", "--events", "--triggers",
            "--hex-blob", "--no-tablespaces", "--databases", str(database["NAME"]),
        ]
        with partial_path.open("xb") as dump:
            result = subprocess.run(command, stdout=dump, stderr=subprocess.DEVNULL, check=False)
        if result.returncode != 0 or partial_path.stat().st_size == 0:
            partial_path.unlink(missing_ok=True)
            print(f"MySQL dump failed (exit code {result.returncode}); partial output removed.")
            return 1
        os.replace(partial_path, output)
        print(f"MySQL backup completed: {output.name}")
        return 0
    except Exception as exc:
        partial_path.unlink(missing_ok=True)
        print(f"MySQL backup failed ({type(exc).__name__}); partial output removed.")
        return 1
    finally:
        if defaults_path:
            defaults_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
