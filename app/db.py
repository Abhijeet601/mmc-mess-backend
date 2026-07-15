import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pymysql
from pymysql.cursors import DictCursor

from .config import BASE_DIR, MYSQL_DATABASE, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_USER


def row_to_dict(row: dict | None) -> dict | None:
    return row


def _connect(database: str | None = MYSQL_DATABASE):
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


def _mysql_sql(sql: str) -> str:
    sql = sql.replace("INSERT OR IGNORE", "INSERT IGNORE")
    # PyMySQL uses Python's percent interpolation for bound parameters. Escape
    # literal percent signs before translating our portable `?` placeholders.
    sql = sql.replace("%", "%%")
    return re.sub(r"\?", "%s", sql)


class MySQLDatabase:
    def __init__(self):
        self.conn = _connect()

    def execute(self, sql: str, params=None):
        cursor = self.conn.cursor()
        cursor.execute(_mysql_sql(sql), params or ())
        return cursor

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def close(self) -> None:
        self.conn.close()


@contextmanager
def get_db() -> Iterator[MySQLDatabase]:
    db = MySQLDatabase()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _split_sql(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False

    for char in script:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double

        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def init_db() -> None:
    server_conn = _connect(database=None)
    try:
        with server_conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        server_conn.commit()
    finally:
        server_conn.close()

    schema_path = Path(BASE_DIR) / "mysql_schema.sql"
    raw_script = schema_path.read_text(encoding="utf-8")
    script = "\n".join(
        line for line in raw_script.splitlines()
        if not line.lstrip().startswith("--")
    )
    with get_db() as db:
        for statement in _split_sql(script):
            stripped = statement.strip()
            if stripped and not stripped.startswith("--"):
                db.execute(stripped)
        # Safe additive migrations for databases created by earlier releases.
        columns = {row["COLUMN_NAME"] for row in db.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'payments'",
            (MYSQL_DATABASE,),
        ).fetchall()}
        if "remarks" not in columns:
            db.execute("ALTER TABLE payments ADD COLUMN remarks TEXT NULL")
        if "receipt_url" not in columns:
            db.execute("ALTER TABLE payments ADD COLUMN receipt_url TEXT NULL")
        student_columns = {row["COLUMN_NAME"] for row in db.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'students'",
            (MYSQL_DATABASE,),
        ).fetchall()}
        if "department" not in student_columns:
            db.execute("ALTER TABLE students ADD COLUMN department VARCHAR(120) NULL AFTER course")
        if "semester" not in student_columns:
            db.execute("ALTER TABLE students ADD COLUMN semester VARCHAR(40) NULL AFTER academic_year")
