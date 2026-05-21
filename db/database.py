import sqlite3
import os
from config import DB_PATH

def get_conn():
    os.makedirs(str(DB_PATH.parent), exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def _ensure_col(conn, table, col, col_def):
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {r[1] for r in cur.fetchall()}
    if col not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")

def init_db():
    conn = get_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            upload_date TEXT NOT NULL,
            period TEXT,
            record_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'loaded'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            inn TEXT,
            contract_start TEXT,
            contract_end TEXT,
            duration INTEGER,
            status TEXT,
            support_type TEXT,
            executor TEXT,
            responsible TEXT,
            direction_responsible TEXT,
            upload_id INTEGER,
            source_filename TEXT,
            UNIQUE(name, inn)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            contract_end_date TEXT,
            event_completed TEXT,
            event_planned TEXT,
            has_completed TEXT,
            has_planned TEXT,
            has_completed_or_postponed TEXT,
            has_planned_after TEXT,
            responsible TEXT,
            period TEXT NOT NULL,
            upload_id INTEGER,
            source_filename TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            doc_number TEXT,
            complaint_date TEXT,
            employee TEXT,
            status TEXT,
            category TEXT,
            upload_id INTEGER,
            source_filename TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rejected_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            order_date TEXT,
            executor TEXT,
            responsible TEXT,
            order_status TEXT NOT NULL,
            upload_id INTEGER,
            source_filename TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS renewal_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            manager TEXT,
            support_type TEXT,
            has_invoice INTEGER DEFAULT 0,
            invoice_number TEXT,
            invoice_date TEXT,
            invoice_amount TEXT,
            upload_id INTEGER,
            source_filename TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS unsigned_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            doc_number TEXT,
            doc_date TEXT,
            doc_status TEXT,
            department TEXT,
            employee TEXT,
            upload_id INTEGER,
            source_filename TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS traffic_light_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            client_name TEXT NOT NULL,
            client_inn TEXT,
            manager TEXT,
            contract_end TEXT,
            calc_date TEXT NOT NULL,
            period_label TEXT,
            crit_event_quarter INTEGER,
            crit_no_complaints INTEGER,
            crit_no_rejected_orders INTEGER,
            crit_event_before_end INTEGER,
            crit_invoice_before_end INTEGER,
            crit_no_unsigned_docs INTEGER,
            critical_bad INTEGER DEFAULT 0,
            auxiliary_bad INTEGER DEFAULT 0,
            final_color TEXT DEFAULT 'green'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS traffic_light_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            calc_date TEXT NOT NULL,
            criterion_id TEXT NOT NULL,
            criterion_name TEXT NOT NULL,
            status INTEGER NOT NULL,
            reasoning TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS traffic_light_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            final_color TEXT NOT NULL,
            calc_date TEXT NOT NULL,
            period_label TEXT NOT NULL
        )
    """)

    for t in ["events", "complaints", "rejected_orders", "renewal_invoices", "unsigned_docs"]:
        _ensure_col(conn, t, "source_filename", "source_filename TEXT")

    for t in ["events", "complaints", "rejected_orders"]:
        _ensure_col(conn, t, "source_filename", "source_filename TEXT")

    indices = [
        ("idx_events_client", "events", "client_name"),
        ("idx_events_period", "events", "period"),
        ("idx_complaints_client", "complaints", "client_name"),
        ("idx_rejected_orders_client", "rejected_orders", "client_name"),
        ("idx_invoices_client", "renewal_invoices", "client_name"),
        ("idx_unsigned_client", "unsigned_docs", "client_name"),
        ("idx_traffic_client", "traffic_light_results", "client_name"),
        ("idx_traffic_details_client", "traffic_light_details", "client_name"),
        ("idx_snapshot_client", "traffic_light_snapshots", "client_name"),
        ("idx_snapshot_period", "traffic_light_snapshots", "period_label"),
    ]
    for name, table, col in indices:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({col})")
        except Exception:
            pass

    conn.commit()
    conn.close()

def clear_all_data():
    conn = get_conn()
    tables = ["traffic_light_details", "traffic_light_results", "traffic_light_snapshots", "unsigned_docs",
              "renewal_invoices", "rejected_orders", "complaints", "events",
              "clients", "source_uploads"]
    for t in tables:
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()
