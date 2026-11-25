"""Database backup / restore.

* SQLite   -> online-consistent copy with sqlite3's backup API (safe while the app runs).
* PostgreSQL -> ``pg_dump --format=custom`` / ``pg_restore`` (PostgreSQL client tools must be installed).
The database password is passed through the PGPASSWORD environment variable, never on the command line.
Backup files are created with mode 0600 (they contain personal data) and live in ``backups/`` (git-ignored).
"""
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url


class BackupError(RuntimeError):
    pass


def _url(uri):
    return make_url(uri)


def kind(uri):
    name = _url(uri).get_backend_name()
    if name not in ("sqlite", "postgresql"):
        raise BackupError(f"Unsupported database backend: {name}")
    return name


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _pg_args(uri):
    u = _url(uri)
    host = u.host or u.query.get("host")
    port = u.port or u.query.get("port")
    args = []
    if host:
        args += ["--host", str(host)]
    if port:
        args += ["--port", str(port)]
    if u.username:
        args += ["--username", u.username]
    env = dict(os.environ)
    if u.password:
        env["PGPASSWORD"] = u.password
    if u.query.get("sslmode"):
        env["PGSSLMODE"] = str(u.query["sslmode"])
    return args, env, u.database


def _require(tool):
    if not shutil.which(tool):
        raise BackupError(f"'{tool}' not found. Install the PostgreSQL client tools (postgresql-client).")


def backup(uri, out_dir, keep=0):
    """Create a backup file and return its path. ``keep`` > 0 prunes older backups."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    k = kind(uri)
    if k == "sqlite":
        src = _url(uri).database
        if not src or src == ":memory:" or not Path(src).exists():
            raise BackupError("SQLite database file not found.")
        dest = out_dir / f"wahj-{_stamp()}.sqlite3"
        with sqlite3.connect(src) as s, sqlite3.connect(dest) as d:
            s.backup(d)
    else:
        _require("pg_dump")
        args, env, db = _pg_args(uri)
        dest = out_dir / f"wahj-{_stamp()}.pgdump"
        r = subprocess.run(["pg_dump", *args, "--format=custom", "--no-owner", "--no-privileges",
                            "--file", str(dest), db], env=env, capture_output=True, text=True)
        if r.returncode:
            dest.unlink(missing_ok=True)
            raise BackupError("pg_dump failed: " + r.stderr.strip()[:300])
    os.chmod(dest, 0o600)
    if keep:
        files = sorted(out_dir.glob("wahj-*.sqlite3")) + sorted(out_dir.glob("wahj-*.pgdump"))
        for old in sorted(files)[:-keep]:
            old.unlink()
    return dest


def restore(uri, file, safety_dir):
    """Restore ``file`` into the configured database. A safety backup of the current
    state is taken first; returns its path (or None if there was nothing to save)."""
    file = Path(file)
    if not file.is_file():
        raise BackupError(f"Backup file not found: {file}")
    k = kind(uri)
    if file.suffix != (".sqlite3" if k == "sqlite" else ".pgdump"):
        raise BackupError(f"This backup file does not match the configured {k} database.")
    safety = None
    try:
        safety = backup(uri, safety_dir)
    except BackupError:
        safety = None  # empty/new database: nothing to protect
    if k == "sqlite":
        with sqlite3.connect(file) as probe:
            if probe.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BackupError("The backup file failed the SQLite integrity check.")
        dst = _url(uri).database
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(file) as s, sqlite3.connect(dst) as d:
            s.backup(d)
    else:
        _require("pg_restore")
        args, env, db = _pg_args(uri)
        r = subprocess.run(["pg_restore", *args, "--clean", "--if-exists", "--no-owner", "--no-privileges",
                            "--single-transaction", "--dbname", db, str(file)], env=env, capture_output=True, text=True)
        if r.returncode:
            raise BackupError("pg_restore failed (database left unchanged): " + r.stderr.strip()[:300])
    return safety
