import os
import tempfile
from datetime import datetime
from pathlib import Path

from db.database import get_conn
from etl.file_detector import detect_file_type
from etl.load_clients import load_clients
from etl.load_events import load_events_from_file
from etl.load_complaints import load_complaints
from etl.load_orders import load_orders
from etl.load_unsigned_docs import load_unsigned_docs
from etl.load_invoices import load_invoices


def check_conflicts(file_type, period):
    conn = get_conn()
    conflicts = []

    if file_type == "clients":
        cur = conn.execute("SELECT COUNT(*) FROM clients")
        count = cur.fetchone()[0]
        if count > 0:
            cur.execute("SELECT name FROM clients ORDER BY RANDOM() LIMIT 5")
            samples = [r[0] for r in cur.fetchall()]
            conflicts.append({
                "table": "clients",
                "count": count,
                "samples": samples,
                "message": f"В базе уже есть {count} клиентов",
            })

    elif file_type == "events" and period:
        cur = conn.execute("SELECT COUNT(*) FROM events WHERE period=?", (period,))
        count = cur.fetchone()[0]
        if count > 0:
            conflicts.append({
                "table": "events",
                "count": count,
                "period": period,
                "message": f"В базе уже есть {count} событий за период '{period}'",
            })

    elif file_type == "complaints":
        cur = conn.execute("SELECT COUNT(*) FROM complaints")
        count = cur.fetchone()[0]
        if count > 0:
            conflicts.append({
                "table": "complaints",
                "count": count,
                "message": f"В базе уже есть {count} жалоб",
            })

    elif file_type == "orders":
        cur = conn.execute("SELECT COUNT(*) FROM rejected_orders")
        count = cur.fetchone()[0]
        if count > 0:
            conflicts.append({
                "table": "rejected_orders",
                "count": count,
                "message": f"В базе уже есть {count} нарядов",
            })

    elif file_type == "unsigned_docs":
        cur = conn.execute("SELECT COUNT(*) FROM unsigned_docs")
        count = cur.fetchone()[0]
        if count > 0:
            conflicts.append({
                "table": "unsigned_docs",
                "count": count,
                "message": f"В базе уже есть {count} записей неподписанных документов",
            })

    elif file_type == "invoices":
        cur = conn.execute("SELECT COUNT(*) FROM renewal_invoices")
        count = cur.fetchone()[0]
        if count > 0:
            conflicts.append({
                "table": "renewal_invoices",
                "count": count,
                "message": f"В базе уже есть {count} записей счетов на продление",
            })

    conn.close()
    return conflicts


def resolve_conflicts(file_type, period, resolution, upload_id):
    conn = get_conn()

    if resolution == "replace":
        if file_type == "clients":
            conn.execute("DELETE FROM clients")
            conn.execute("DELETE FROM traffic_light_results")
        elif file_type == "events" and period:
            conn.execute("DELETE FROM events WHERE period=?", (period,))
        elif file_type == "complaints":
            conn.execute("DELETE FROM complaints")
        elif file_type == "orders":
            conn.execute("DELETE FROM rejected_orders")
        elif file_type == "unsigned_docs":
            conn.execute("DELETE FROM unsigned_docs")
        elif file_type == "invoices":
            conn.execute("DELETE FROM renewal_invoices")

        conn.execute("DELETE FROM source_uploads WHERE file_type=? AND (period=? OR period IS NULL)",
                     (file_type, period or ""))
    elif resolution == "skip":
        conn.execute("DELETE FROM source_uploads WHERE id=?", (upload_id,))

    conn.commit()
    conn.close()


def load_file_by_path(filepath, upload_id, resolution="replace_if_conflict"):
    filepath = Path(filepath) if isinstance(filepath, str) else filepath
    filename = filepath.name

    with open(filepath, "rb") as f:
        file_bytes = f.read()

    import io
    buf = io.BytesIO(file_bytes)
    detection = detect_file_type(filename, buf)

    if detection["file_type"] == "unknown":
        return {"success": False, "detection": detection, "loaded": 0,
                "error": f"Не удалось определить тип файла: {filename}"}

    if resolution == "replace_if_conflict":
        conflicts = check_conflicts(detection["file_type"], detection["period"])
        if conflicts:
            return {"success": False, "detection": detection, "loaded": 0,
                    "conflicts": conflicts, "needs_resolution": True}

    return _execute_load(filepath, detection, upload_id, resolution)


def load_file_by_buffer(file_buffer, filename, upload_id, resolution="replace_if_conflict"):
    file_buffer.seek(0)
    detection = detect_file_type(filename, file_buffer)

    if detection["file_type"] == "unknown":
        return {"success": False, "detection": detection, "loaded": 0,
                "error": f"Не удалось определить тип файла: {filename}"}

    if resolution == "replace_if_conflict":
        conflicts = check_conflicts(detection["file_type"], detection["period"])
        if conflicts:
            return {"success": False, "detection": detection, "loaded": 0,
                    "conflicts": conflicts, "needs_resolution": True}

    file_buffer.seek(0)
    return _execute_load(file_buffer, detection, upload_id, resolution)


def _execute_load(source, detection, upload_id, resolution):
    ft = detection["file_type"]
    period = detection["period"]
    label = detection.get("label", ft)
    fname_safe = label

    conn = get_conn()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO source_uploads (file_name, file_type, period, upload_date, status)
        VALUES (?,?,?,?,?)
    """, (label, ft, period or "", now, "loading"))
    file_upload_id = conn.lastrowid
    conn.commit()
    conn.close()

    try:
        kwargs = {"upload_id": upload_id, "source_filename": fname_safe}
        if ft == "clients":
            cnt = load_clients(source=source, **kwargs)
        elif ft == "events":
            cnt = load_events_from_file(source, period, upload_id, source_filename=fname_safe)
        elif ft == "complaints":
            cnt = load_complaints(source=source, **kwargs)
        elif ft == "orders":
            cnt = load_orders(source=source, **kwargs)
        elif ft == "unsigned_docs":
            cnt = load_unsigned_docs(source=source, **kwargs)
        elif ft == "invoices":
            cnt = load_invoices(source=source, **kwargs)
        else:
            cnt = 0

        conn = get_conn()
        conn.execute("UPDATE source_uploads SET status='completed', record_count=? WHERE id=?",
                     (cnt, file_upload_id))
        conn.commit()
        conn.close()

        return {"success": True, "detection": detection, "loaded": cnt,
                "file_upload_id": file_upload_id}

    except Exception as e:
        conn = get_conn()
        conn.execute("UPDATE source_uploads SET status='error' WHERE id=?", (file_upload_id,))
        conn.commit()
        conn.close()
        return {"success": False, "detection": detection, "loaded": 0, "error": str(e)}


def load_folder(folder_path, upload_id, resolution="replace"):
    folder = Path(folder_path)
    total_loaded = 0
    results = []

    for ext in ["*.xls", "*.xlsx", "*.XLS", "*.XLSX"]:
        for filepath in sorted(folder.glob(ext)):
            result = load_file_by_path(filepath, upload_id, resolution=resolution)
            results.append(result)
            if result["success"]:
                total_loaded += result["loaded"]

    return {"success": True, "total_loaded": total_loaded, "results": results}
