"""Create the sanitized SQLite/filesystem payload shipped with the desktop installer."""
from __future__ import annotations

import shutil
import sqlite3
import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = ROOT / "data" / "app.db"
SOURCE_FILES = ROOT / "data"
OUTPUT = ROOT / "desktop" / "demo-data"
DEMO_DB = OUTPUT / "app.db"
PATH_TOKEN = "__DEMO_DATA_DIR__\\"


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def create_database() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if not SOURCE_DB.exists():
        if DEMO_DB.exists():
            print(f"Using checked-in demo data package: {OUTPUT}")
            return
        raise FileNotFoundError(f"Neither source database nor demo package exists: {SOURCE_DB}")
    if DEMO_DB.exists():
        DEMO_DB.unlink()

    with sqlite3.connect(SOURCE_DB) as source, sqlite3.connect(DEMO_DB) as target:
        source.backup(target)
        target.execute("PRAGMA foreign_keys=OFF")

        sensitive_values: set[str] = set()
        users = target.execute("SELECT id, username, email, phone, enterprise_name, role FROM users").fetchall()
        for _id, username, email, phone, enterprise, _role in users:
            sensitive_values.update(str(value) for value in (username, email, phone, enterprise) if value)

        profile_rows = target.execute(
            "SELECT real_name, display_name, school FROM learner_profiles"
        ).fetchall()
        for row in profile_rows:
            sensitive_values.update(str(value) for value in row if value)

        # Remove fixed administrator credentials. The desktop bootstrap screen
        # creates a fresh local administrator on first launch.
        target.execute("DELETE FROM users WHERE role = 'ADMIN'")
        target.execute("DELETE FROM user_ai_configs")

        try:
            import bcrypt

            disabled_hash = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode("ascii")
        except ImportError:
            # These accounts are inactive; this fallback is only for environments
            # that do not have the build venv available when preparing the payload.
            disabled_hash = "$2b$12$McleRMh2wkTvQomOyV0bQ.iJpyAxyeYkvl5NY169fmZbuR2We6KYa"

        learner_number = 0
        teacher_number = 0
        for user_id, _username, _email, _phone, _enterprise, role in users:
            if role == "ADMIN":
                continue
            if role == "TEACHER":
                teacher_number += 1
                demo_name = f"demo_teacher_{teacher_number:03d}"
            else:
                learner_number += 1
                demo_name = f"demo_learner_{learner_number:03d}"
            target.execute(
                "UPDATE users SET username = ?, password_hash = ?, email = NULL, phone = NULL, "
                "enterprise_name = NULL, is_active = 0, is_verified = 1, last_login_at = NULL "
                "WHERE id = ?",
                (demo_name, disabled_hash, user_id),
            )

        # Replace personally identifying text that may be embedded in audit or
        # generated JSON fields. Content and metrics themselves remain intact.
        table_names = [row[0] for row in target.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )]
        for table in table_names:
            columns = [row[1] for row in target.execute(f"PRAGMA table_info({quote(table)})") if row[2].upper() in {"TEXT", "VARCHAR", "JSON"}]
            for column in columns:
                rows = target.execute(
                    f"SELECT rowid, {quote(column)} FROM {quote(table)} WHERE {quote(column)} IS NOT NULL"
                ).fetchall()
                for rowid, value in rows:
                    if not isinstance(value, str):
                        continue
                    replacement = value
                    for sensitive in sensitive_values:
                        replacement = replacement.replace(sensitive, "演示用户")
                    if table == "audit_logs" and column == "username":
                        replacement = "demo_operator"
                    if replacement != value:
                        target.execute(
                            f"UPDATE {quote(table)} SET {quote(column)} = ? WHERE rowid = ?",
                            (replacement, rowid),
                        )

        # Knowledge files are copied beside the database during first launch.
        target.execute(
            "UPDATE knowledge_docs SET file_path = ? || substr(file_path, instr(file_path, 'knowledge_docs')) "
            "WHERE file_path IS NOT NULL AND instr(file_path, 'knowledge_docs') > 0",
            (PATH_TOKEN,),
        )
        target.commit()

    for directory in ("knowledge_docs", "resources", "uploads"):
        source = SOURCE_FILES / directory
        destination = OUTPUT / directory
        if destination.exists():
            shutil.rmtree(destination)
        if source.exists():
            shutil.copytree(source, destination)


if __name__ == "__main__":
    create_database()
    print(f"Demo data package created: {OUTPUT}")
