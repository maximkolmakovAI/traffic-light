from datetime import datetime, date
from db.database import get_conn

def check_crit_event_quarter(conn, client_name):
    cur = conn.execute("""
        SELECT period, has_completed_or_postponed FROM events
        WHERE client_name = ? AND period IN ('февраль','март','апрель')
    """, (client_name,))
    rows = cur.fetchall()
    details = []
    for r in rows:
        val = str(r[1]).strip().lower() if r[1] else ""
        is_ok = val in ("да", "yes", "true", "1")
        details.append(f"{r[0]}: {r[1] or 'нет данных'}")
    ok = any(
        str(r[1]).strip().lower() in ("да", "yes", "true", "1")
        for r in rows
    )
    reason = "; ".join(details) if details else "Нет записей о событиях"
    return ok, reason


def check_crit_no_complaints(conn, client_name):
    cur = conn.execute("SELECT doc_number, status FROM complaints WHERE client_name = ?", (client_name,))
    rows = cur.fetchall()
    ok = len(rows) == 0
    if ok:
        return True, "Клиент отсутствует в списке жалоб"
    complaints = "; ".join(f"{r[0]} ({r[1]})" for r in rows)
    return False, f"Есть жалобы: {complaints}"


def check_crit_no_rejected_orders(conn, client_name):
    cur = conn.execute("""
        SELECT order_date, order_status FROM rejected_orders
        WHERE client_name = ? AND LOWER(order_status) LIKE '%отклонен%'
    """, (client_name,))
    rows = cur.fetchall()
    ok = len(rows) == 0
    if ok:
        return True, "Нет нарядов со статусом 'отклонен клиентом'"
    details = "; ".join(f"{r[0]} статус={r[1]}" for r in rows)
    return False, f"Есть отклоненные наряды: {details}"


def is_near_end(contract_end_str):
    if not contract_end_str or contract_end_str in ("", "nan", "None"):
        return False
    end_date = parse_date(contract_end_str)
    if not end_date:
        return False
    today = date.today()
    days_to_end = (end_date - today).days
    return 30 <= days_to_end <= 90


def check_crit_event_before_end(conn, client_name, contract_end_str):
    if not is_near_end(contract_end_str):
        return None, "Не применимо (договор заканчивается не через 30-90 дней)"
    try:
        cur = conn.execute("""
            SELECT has_completed_or_postponed, period, source_filename
            FROM events WHERE client_name = ? AND period = 'апрель'
            ORDER BY id DESC LIMIT 1
        """, (client_name,))
        row = cur.fetchone()
        if row:
            val = str(row[0]).strip().lower() if row[0] else ""
            ok = val in ("да", "yes", "true", "1")
            src = row[2] or "неизвестный файл"
            if ok:
                return True, f"Событие есть в апрельском отчете ({src})"
            return False, f"События нет в апрельском отчете ({src}), значение: {row[0]}"
        return False, "Нет данных о событиях за апрель"
    except Exception as e:
        return False, f"Ошибка: {e}"


def check_crit_invoice_before_end(conn, client_name, contract_end_str):
    if not is_near_end(contract_end_str):
        return None, "Не применимо (договор заканчивается не через 30-90 дней)"
    try:
        cur = conn.execute("""
            SELECT has_invoice, invoice_number, source_filename
            FROM renewal_invoices WHERE client_name = ?
        """, (client_name,))
        row = cur.fetchone()
        src = row[2] if row and row[2] else "неизвестный файл"
        if row and row[0]:
            return True, f"Счет на продление есть ({row[1] or 'номер не указан'}), файл: {src}"
        if row:
            return False, f"Счет на продление отсутствует, файл: {src}"
        return False, f"Клиент не найден в отчете 'Счета на продление'"
    except Exception as e:
        return False, f"Ошибка: {e}"


def check_crit_no_unsigned_docs(conn, client_name):
    cur = conn.execute("""
        SELECT doc_status, source_filename FROM unsigned_docs WHERE client_name = ?
    """, (client_name,))
    rows = cur.fetchall()
    if not rows:
        return True, "Клиент отсутствует в списке неподписанных документов"
    src = rows[0][1] if rows[0][1] else "неизвестный файл"
    return False, f"Клиент найден в отчете 'Неподписанные документы', файл: {src}"


def parse_date(s):
    s = str(s).strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
