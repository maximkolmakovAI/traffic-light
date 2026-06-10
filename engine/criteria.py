from datetime import datetime, date
from db.database import get_conn
from etl.egrul_checker import check_by_inn


def check_crit_liquidation(conn, client_name):
    cur = conn.execute("SELECT inn FROM clients WHERE name = ?", (client_name,))
    row = cur.fetchone()
    inn = str(row[0]).strip() if row and row[0] and str(row[0]) not in ("", "nan", "None") else ""

    if not inn:
        return True, "Нет ИНН для проверки"

    # check DB first
    cur = conn.execute(
        "SELECT liquidation_status, check_date FROM liquidation_data WHERE inn = ? ORDER BY id DESC LIMIT 1",
        (inn,),
    )
    db_row = cur.fetchone()
    if db_row:
        status = db_row[0]
        check_date_str = db_row[1]
        try:
            check_dt = datetime.fromisoformat(check_date_str) if check_date_str else None
        except Exception:
            check_dt = None
        from config import LIQUIDATION_CACHE_DAYS
        if check_dt and (datetime.now() - check_dt).days < LIQUIDATION_CACHE_DAYS:
            if status in ("LIQUIDATING", "LIQUIDATED", "BANKRUPT", "REORGANIZING"):
                return False, _liq_reason(status, db_row)
            return True, _liq_reason(status, db_row)

    result = check_by_inn(inn)
    status = result.get("status", "unknown")
    liq_date = result.get("liquidation_date")

    conn.execute(
        """INSERT INTO liquidation_data (client_name, inn, liquidation_status, liquidation_date, check_date, source)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (client_name, inn, status, liq_date, datetime.now().isoformat(), result.get("source", "dadata")),
    )
    conn.commit()

    if status in ("LIQUIDATING", "LIQUIDATED", "BANKRUPT", "REORGANIZING"):
        return False, _liq_reason(status, {"liquidation_status": status, "liquidation_date": liq_date})
    return True, _liq_reason(status, {"liquidation_status": status, "liquidation_date": liq_date})


def _liq_reason(status, row):
    status_labels = {
        "ACTIVE": "действующая",
        "LIQUIDATING": "в процессе ликвидации",
        "LIQUIDATED": "ликвидирована",
        "BANKRUPT": "банкротство",
        "REORGANIZING": "реорганизация/присоединение",
        "unknown": "статус не определён",
    }
    label = status_labels.get(status, status)
    liq_date = row.get("liquidation_date") if isinstance(row, dict) else (row[2] if len(row) > 2 else "")
    if liq_date:
        try:
            ts_ms = int(liq_date)
            d = datetime.fromtimestamp(ts_ms / 1000).strftime("%d.%m.%Y")
            return f"{label} ({d})"
        except (ValueError, TypeError):
            return f"{label} ({liq_date})"
    return label

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
    """True если до окончания договора <= 67 дней (включая просроченные)."""
    if not contract_end_str or contract_end_str in ("", "nan", "None"):
        return False
    end_date = parse_date(contract_end_str)
    if not end_date:
        return False
    today = date.today()
    days_to_end = (end_date - today).days
    return days_to_end <= 67


def _days_until(contract_end_str):
    """Число дней до окончания договора (отрицательное если просрочен)."""
    end_date = parse_date(contract_end_str)
    if not end_date:
        return None
    return (end_date - date.today()).days


def check_crit_event_before_end(conn, client_name, contract_end_str):
    if not is_near_end(contract_end_str):
        return True, "OK (договор > 67 дней)"
    try:
        days = _days_until(contract_end_str)
        cur = conn.execute("""
            SELECT has_completed_or_postponed, period, source_filename
            FROM events WHERE client_name = ?
            ORDER BY id DESC LIMIT 1
        """, (client_name,))
        row = cur.fetchone()
        if row:
            val = str(row[0]).strip().lower() if row[0] else ""
            ok = val in ("да", "yes", "true", "1")
            src = row[2] or "неизвестный файл"
            if ok:
                return True, f"Событие есть (последнее: {row[1]}), файл: {src}"
            if days is not None and days < 0:
                return False, f"Договор просрочен на {-days} дн., события нет — провал"
            return False, f"До окончания {days} дн., событие отсутствует — провал"
        if days is not None and days < 0:
            return False, f"Договор просрочен на {-days} дн., событий не было"
        return False, "Нет данных о событиях"
    except Exception as e:
        return False, f"Ошибка: {e}"


def check_crit_invoice_before_end(conn, client_name, contract_end_str):
    if not is_near_end(contract_end_str):
        return True, "OK (договор > 67 дней)"
    try:
        days = _days_until(contract_end_str)
        cur = conn.execute("""
            SELECT has_invoice, invoice_number, source_filename
            FROM renewal_invoices WHERE client_name = ?
        """, (client_name,))
        row = cur.fetchone()
        src = row[2] if row and row[2] else "неизвестный файл"
        if row and row[0]:
            return True, f"Счет на продление есть ({row[1] or 'номер не указан'}), файл: {src}"
        if days is not None and days < 0:
            return False, f"Договор просрочен на {-days} дн., счета нет — провал"
        if row:
            return False, f"Счет на продление отсутствует, файл: {src}"
        if days is not None and days < 0:
            return False, f"Договор просрочен на {-days} дн., клиент не в отчете"
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
    return False, "есть неподписанные"


def parse_date(s):
    s = str(s).strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
