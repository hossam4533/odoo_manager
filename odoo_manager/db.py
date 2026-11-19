"""PostgreSQL helpers: list databases, Odoo-style zip backup & restore."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import zipfile

import psycopg2

from .i18n import tr
from .core import CREATE_NO_WINDOW, Instance, conf_value


def _params(inst: Instance) -> dict:
    c = inst.conf
    return {
        "host": conf_value(c, "db_host", "localhost"),
        "port": int(conf_value(c, "db_port", "5432")),
        "user": conf_value(c, "db_user", os.environ.get("USERNAME", "odoo")),
        "password": conf_value(c, "db_password", ""),
    }


def _env(inst: Instance) -> dict:
    p = _params(inst)
    env = dict(os.environ)
    env.update(PGHOST=p["host"], PGPORT=str(p["port"]), PGUSER=p["user"], PGPASSWORD=p["password"])
    return env


def list_databases(inst: Instance) -> list[tuple[str, str]]:
    """[(name, size)] of databases owned by the instance's db_user."""
    p = _params(inst)
    con = psycopg2.connect(dbname="postgres", connect_timeout=5, **p)
    try:
        with con.cursor() as cr:
            cr.execute("""
                SELECT d.datname, pg_size_pretty(pg_database_size(d.datname))
                  FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba
                 WHERE NOT d.datistemplate AND d.datname <> 'postgres' AND r.rolname = %s
              ORDER BY d.datname""", (p["user"],))
            return cr.fetchall()
    finally:
        con.close()


def _run(cmd: list[str], env: dict, log) -> None:
    log(" ".join(os.path.basename(cmd[0]) if i == 0 else a for i, a in enumerate(cmd)))
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"exit code {r.returncode}")


def backup(inst: Instance, dbname: str, pg_bin: str, dest_dir: str, log=print) -> str:
    """Create an Odoo-compatible backup zip (dump.sql + filestore). Returns zip path."""
    pg_dump = os.path.join(pg_bin, "pg_dump.exe")
    if not os.path.exists(pg_dump):
        raise RuntimeError(tr("no_pgdump", p=pg_bin))
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, f"{dbname}_{time.strftime('%Y-%m-%d_%H-%M-%S')}.zip")
    with tempfile.TemporaryDirectory() as tmp:
        sql = os.path.join(tmp, "dump.sql")
        _run([pg_dump, "--no-owner", "--format=p", "-f", sql, dbname], _env(inst), log)
        filestore = os.path.join(inst.data_dir, "filestore", dbname)
        log(tr("zipping"))
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.write(sql, "dump.sql")
            if os.path.isdir(filestore):
                for root, _, files in os.walk(filestore):
                    for f in files:
                        full = os.path.join(root, f)
                        z.write(full, os.path.join("filestore", os.path.relpath(full, filestore)))
            else:
                log(tr("no_filestore", p=filestore))
    log(tr("done_path", p=out))
    return out


def restore(inst: Instance, zip_path: str, new_db: str, pg_bin: str, log=print) -> None:
    psql = os.path.join(pg_bin, "psql.exe")
    createdb = os.path.join(pg_bin, "createdb.exe")
    pg_restore = os.path.join(pg_bin, "pg_restore.exe")
    env = _env(inst)
    if new_db in [n for n, _ in list_databases(inst)]:
        raise RuntimeError(tr("db_exists", n=new_db))
    ext = os.path.splitext(zip_path)[1].lower()
    if ext in (".dump", ".backup"):                 # pg_dump custom format
        _run([createdb, "-T", "template0", "-E", "UTF8", new_db], env, log)
        _run([pg_restore, "--no-owner", "-d", new_db, zip_path], env, log)
        log(tr("restore_done", n=new_db))
        return
    if ext == ".sql":                               # plain SQL dump
        _run([createdb, "-T", "template0", "-E", "UTF8", new_db], env, log)
        _run([psql, "-q", "-v", "ON_ERROR_STOP=0", "-d", new_db, "-f", zip_path], env, log)
        log(tr("restore_done", n=new_db))
        return
    with tempfile.TemporaryDirectory() as tmp:
        log(tr("unzipping"))
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        sql = os.path.join(tmp, "dump.sql")
        if not os.path.exists(sql):
            raise RuntimeError(tr("no_dump"))
        _run([createdb, "-T", "template0", "-E", "UTF8", new_db], env, log)
        _run([psql, "-q", "-v", "ON_ERROR_STOP=0", "-d", new_db, "-f", sql], env, log)
        src = os.path.join(tmp, "filestore")
        if os.path.isdir(src):
            dst = os.path.join(inst.data_dir, "filestore", new_db)
            log(tr("copy_filestore", p=dst))
            shutil.copytree(src, dst, dirs_exist_ok=True)
    log(tr("restore_done", n=new_db))


def drop(inst: Instance, dbname: str, pg_bin: str, log=print) -> None:
    _run([os.path.join(pg_bin, "dropdb.exe"), "--if-exists", "--force", dbname], _env(inst), log)
    fs = os.path.join(inst.data_dir, "filestore", dbname)
    if os.path.isdir(fs):
        shutil.rmtree(fs, ignore_errors=True)
