#!/usr/bin/env python3
"""Import data from a local sqlite `rss.db` into a PostgreSQL database.

Usage:
  export DATABASE_URL=postgresql://user:pass@host:5432/dbname
  python scripts/import_sqlite_to_postgres.py --sqlite rss.db

Notes:
- This script assumes the target Postgres database already has the
  appropriate schema applied (migrations). It will copy rows and preserve
  integer primary keys where possible, then adjust sequences to avoid
  future conflicts.
- Review and run in a staging DB first.
"""
import argparse
import os
import sqlite3
import sys

import psycopg2
from psycopg2.extras import execute_values


TABLES = [
    "users",
    "feeds",
    "subscriptions",
    "stories",
    "read_states",
    "waitlist_signups",
]


def copy_table(sqlite_conn, pg_conn, table):
    s_cur = sqlite_conn.cursor()
    p_cur = pg_conn.cursor()

    s_cur.execute(f"SELECT * FROM {table}")
    rows = s_cur.fetchall()
    if not rows:
        print(f"{table}: no rows to copy")
        return

    col_names = [d[0] for d in s_cur.description]
    placeholders = ",".join(["%s"] * len(col_names))
    cols = ",".join(col_names)

    insert_sql = f"INSERT INTO {table} ({cols}) VALUES %s ON CONFLICT DO NOTHING"

    # execute_values is efficient for bulk insert
    execute_values(p_cur, insert_sql, rows)
    pg_conn.commit()

    # If table has an integer primary key 'id', set sequence to max(id)
    if "id" in col_names:
        p_cur.execute(f"SELECT MAX(id) FROM {table}")
        max_id = p_cur.fetchone()[0]
        if max_id is not None:
            seq_name = f"{table}_id_seq"
            try:
                p_cur.execute(f"SELECT setval(%s, %s, true)", (seq_name, max_id))
                pg_conn.commit()
            except Exception:
                # Sequence may not exist or be named differently; ignore
                pg_conn.rollback()

    print(f"{table}: copied {len(rows)} rows")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default="rss.db", help="Path to sqlite db")
    parser.add_argument("--pg-url", default=os.environ.get("DATABASE_URL"), help="Postgres DATABASE_URL (env DATABASE_URL)")
    args = parser.parse_args()

    if not args.pg_url:
        print("ERROR: DATABASE_URL not set. Export DATABASE_URL or pass --pg-url.")
        sys.exit(2)

    if not os.path.exists(args.sqlite):
        print(f"ERROR: sqlite file not found: {args.sqlite}")
        sys.exit(2)

    sqlite_conn = sqlite3.connect(args.sqlite)
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = psycopg2.connect(args.pg_url)

    try:
        for table in TABLES:
            copy_table(sqlite_conn, pg_conn, table)
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
