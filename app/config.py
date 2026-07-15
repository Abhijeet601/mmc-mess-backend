import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


def _load_env_file() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

# Mess ERP Database (Read/Write)
MYSQL_HOST = os.getenv("MYSQL_HOST") or os.getenv("MYSQLHOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT") or os.getenv("MYSQLPORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER") or os.getenv("MYSQLUSER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD") or os.getenv("MYSQLPASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE") or os.getenv("MYSQLDATABASE", "mess")

# Poetic Reflection Database (Read-Only Master Student Data)
POETIC_HOST = os.getenv("POETIC_HOST") or os.getenv("POETIC_MYSQLHOST", "127.0.0.1")
POETIC_PORT = int(os.getenv("POETIC_PORT") or os.getenv("POETIC_MYSQLPORT", "3306"))
POETIC_USER = os.getenv("POETIC_USER") or os.getenv("POETIC_MYSQLUSER", "root")
POETIC_PASSWORD = os.getenv("POETIC_PASSWORD") or os.getenv("POETIC_MYSQLPASSWORD", "")
POETIC_DATABASE = os.getenv("POETIC_DATABASE") or os.getenv("POETIC_MYSQLDATABASE", "poetic_reflection")

APP_SECRET = os.getenv("APP_SECRET", "dev-secret-change-before-production")
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "28800"))
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174",
    ).split(",")
    if origin.strip()
]

