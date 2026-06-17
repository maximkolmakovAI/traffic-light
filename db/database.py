import sqlite3
import os
from pathlib import Path
from config import DB_PATH, FALLBACK_DB_PATH

_current_db = DB_PATH

def get_conn(*, db_path=None):
    global _current_db
    path = db_path or _current_db
    os.makedirs(str(path.parent), exist_ok=True)
    for sfx in ["-wal", "-shm"]:
        p = path.parent / (path.name + sfx)
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def _nuke(path):
    for sfx in ["", "-wal", "-shm"]:
        p = path.parent / (path.name + sfx)
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

def _ensure_col(conn, table, col, col_def):
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {r[1] for r in cur.fetchall()}
    if col not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")

def _init_tables(conn):
    creates = [
        "source_uploads", "clients", "events", "complaints",
        "rejected_orders", "renewal_invoices", "unsigned_docs",
        "traffic_light_results", "traffic_light_details",
        "traffic_light_snapshots", "liquidation_data"
    ]
    schemas = {
        "source_uploads": """
            CREATE TABLE IF NOT EXISTS source_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL, file_type TEXT NOT NULL,
                upload_date TEXT NOT NULL, period TEXT,
                record_count INTEGER DEFAULT 0, status TEXT DEFAULT 'loaded'
            )""",
        "clients": """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, inn TEXT,
                contract_start TEXT, contract_end TEXT,
                duration INTEGER, status TEXT, support_type TEXT,
                executor TEXT, responsible TEXT, direction_responsible TEXT,
                upload_id INTEGER, source_filename TEXT,
                UNIQUE(name, inn)
            )""",
        "events": """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL, contract_end_date TEXT,
                event_completed TEXT, event_planned TEXT,
                has_completed TEXT, has_planned TEXT,
                has_completed_or_postponed TEXT, has_planned_after TEXT,
                responsible TEXT, period TEXT NOT NULL,
                upload_id INTEGER, source_filename TEXT
            )""",
        "complaints": """
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL, doc_number TEXT,
                complaint_date TEXT, employee TEXT, status TEXT, category TEXT,
                upload_id INTEGER, source_filename TEXT
            )""",
        "rejected_orders": """
            CREATE TABLE IF NOT EXISTS rejected_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL, order_date TEXT,
                executor TEXT, responsible TEXT, order_status TEXT NOT NULL,
                upload_id INTEGER, source_filename TEXT
            )""",
        "renewal_invoices": """
            CREATE TABLE IF NOT EXISTS renewal_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL, manager TEXT, support_type TEXT,
                has_invoice INTEGER DEFAULT 0, invoice_number TEXT,
                invoice_date TEXT, invoice_amount TEXT,
                upload_id INTEGER, source_filename TEXT
            )""",
        "unsigned_docs": """
            CREATE TABLE IF NOT EXISTS unsigned_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL, doc_number TEXT, doc_date TEXT,
                doc_status TEXT, department TEXT, employee TEXT,
                upload_id INTEGER, source_filename TEXT
            )""",
        "traffic_light_results": """
            CREATE TABLE IF NOT EXISTS traffic_light_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER, client_name TEXT NOT NULL, client_inn TEXT,
                manager TEXT, contract_end TEXT, calc_date TEXT NOT NULL,
                period_label TEXT,
                crit_event_quarter INTEGER, crit_no_complaints INTEGER,
                crit_no_rejected_orders INTEGER, crit_event_before_end INTEGER,
                crit_invoice_before_end INTEGER, crit_no_unsigned_docs INTEGER,
                critical_bad INTEGER DEFAULT 0, auxiliary_bad INTEGER DEFAULT 0,
                final_color TEXT DEFAULT 'green'
            )""",
        "traffic_light_details": """
            CREATE TABLE IF NOT EXISTS traffic_light_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL, calc_date TEXT NOT NULL,
                criterion_id TEXT NOT NULL, criterion_name TEXT NOT NULL,
                status INTEGER NOT NULL, reasoning TEXT NOT NULL
            )""",
        "traffic_light_snapshots": """
            CREATE TABLE IF NOT EXISTS traffic_light_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL, final_color TEXT NOT NULL,
                calc_date TEXT NOT NULL, period_label TEXT NOT NULL
            )""",
        "liquidation_data": """
            CREATE TABLE IF NOT EXISTS liquidation_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT, inn TEXT,
                liquidation_status TEXT DEFAULT 'unknown', liquidation_date TEXT,
                check_date TEXT, source TEXT DEFAULT 'dadata',
                upload_id INTEGER, source_filename TEXT
            )""",
    }
    for name in creates:
        try:
            conn.execute(schemas[name])
        except Exception:
            pass

    for t in ["events", "complaints", "rejected_orders", "renewal_invoices", "unsigned_docs"]:
        try:
            _ensure_col(conn, t, "source_filename", "source_filename TEXT")
        except Exception:
            pass

    try:
        _ensure_col(conn, "traffic_light_results", "crit_liquidation", "crit_liquidation INTEGER DEFAULT 1")
    except Exception:
        pass

    try:
        cur = conn.execute("""
            SELECT COUNT(*) FROM traffic_light_results r
            WHERE r.crit_liquidation = 0
            AND NOT EXISTS (
                SELECT 1 FROM traffic_light_details d
                WHERE d.client_name = r.client_name AND d.criterion_id = 'crit_liquidation'
            )
        """)
        uncalculated = cur.fetchone()[0]
        if uncalculated > 0:
            conn.execute("""
                UPDATE traffic_light_results
                SET crit_liquidation = 1
                WHERE crit_liquidation = 0
                AND NOT EXISTS (
                    SELECT 1 FROM traffic_light_details d
                    WHERE d.client_name = traffic_light_results.client_name AND d.criterion_id = 'crit_liquidation'
                )
            """)
    except Exception:
        pass

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

def _try_init(path):
    conn = get_conn(db_path=path)
    _init_tables(conn)
    conn.close()

def init_db():
    global _current_db
    # Try primary path (persistent data/)
    try:
        _try_init(DB_PATH)
        _current_db = DB_PATH
        return
    except Exception:
        pass
    # Nuke and retry
    _nuke(DB_PATH)
    try:
        _try_init(DB_PATH)
        _current_db = DB_PATH
        return
    except Exception:
        pass
    # Fallback to non-persistent path
    _nuke(FALLBACK_DB_PATH)
    _try_init(FALLBACK_DB_PATH)
    _current_db = FALLBACK_DB_PATH

def get_current_db_path():
    return _current_db

def clear_all_data():
    conn = get_conn()
    tables = ["traffic_light_details", "traffic_light_results", "traffic_light_snapshots",
              "unsigned_docs", "renewal_invoices", "rejected_orders", "complaints",
              "events", "clients", "source_uploads"]
    for t in tables:
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()