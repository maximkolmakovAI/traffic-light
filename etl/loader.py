from datetime import datetime
from db.database import get_conn, clear_all_data, init_db
from etl.load_clients import load_clients
from etl.load_events import load_events
from etl.load_complaints import load_complaints
from etl.load_orders import load_orders
from etl.load_unsigned_docs import load_unsigned_docs
from etl.load_invoices import load_invoices

def run_all_etl(clear_first=True):
    init_db()
    if clear_first:
        print("Clearing existing data...")
        clear_all_data()
    conn = get_conn()
    cur = conn.cursor()

    now = datetime.now().isoformat()
    cur.execute("INSERT INTO source_uploads (file_name, file_type, upload_date, status) VALUES (?,?,?,?)",
                ("мастер-загрузка", "batch", now, "started"))
    batch_id = cur.lastrowid
    conn.commit()
    conn.close()

    print("Loading clients...")
    load_clients(batch_id)

    print("Loading events (февраль, март, апрель)...")
    load_events(batch_id)

    print("Loading complaints...")
    load_complaints(batch_id)

    print("Loading rejected orders...")
    load_orders(batch_id)

    print("Loading unsigned documents...")
    load_unsigned_docs(batch_id)

    print("Loading renewal invoices...")
    load_invoices(batch_id)

    conn = get_conn()
    conn.execute("UPDATE source_uploads SET status='completed' WHERE id=?", (batch_id,))
    conn.commit()
    conn.close()

    print(f"ETL batch {batch_id} completed.")
    return batch_id
