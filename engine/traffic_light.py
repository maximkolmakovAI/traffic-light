from datetime import datetime
from db.database import get_conn
from engine.criteria import (
    check_crit_event_quarter, check_crit_no_complaints,
    check_crit_no_rejected_orders, check_crit_event_before_end,
    check_crit_invoice_before_end, check_crit_no_unsigned_docs,
)

COLOR_GREEN = "green"
COLOR_YELLOW = "yellow"
COLOR_RED = "red"

CRITERIA_SPEC = [
    {"id": "crit_event_quarter", "name": "Событие 1 раз в квартал", "critical": True},
    {"id": "crit_no_complaints", "name": "Отсутствие жалоб за 3 мес", "critical": False},
    {"id": "crit_no_rejected_orders", "name": "Отсутствие нарядов (отклонен клиентом)", "critical": False},
    {"id": "crit_event_before_end", "name": "Событие за 2 мес до окончания", "critical": True},
    {"id": "crit_invoice_before_end", "name": "Счет на продление за 2 мес до окончания", "critical": True},
    {"id": "crit_no_unsigned_docs", "name": "Отсутствие неподписанных документов", "critical": False},
]

def calculate_traffic_light(period_label=None):
    conn = get_conn()
    if not period_label:
        period_label = datetime.now().strftime("%Y-%m")

    cur = conn.execute("SELECT id, name, contract_end, responsible FROM clients")
    clients = cur.fetchall()

    conn.execute("DELETE FROM traffic_light_results")
    conn.execute("DELETE FROM traffic_light_details")
    conn.commit()

    now_str = datetime.now().isoformat()

    for client in clients:
        cid, cname, cend, manager = client
        cname = str(cname) if cname else ""

        details = {}

        ok, reason = check_crit_event_quarter(conn, cname)
        details["crit_event_quarter"] = {"ok": 1 if ok else 0, "reason": reason}

        ok, reason = check_crit_no_complaints(conn, cname)
        details["crit_no_complaints"] = {"ok": 1 if ok else 0, "reason": reason}

        ok, reason = check_crit_no_rejected_orders(conn, cname)
        details["crit_no_rejected_orders"] = {"ok": 1 if ok else 0, "reason": reason}

        ok, reason = check_crit_event_before_end(conn, cname, cend)
        if ok is None:
            details["crit_event_before_end"] = {"ok": 1, "reason": reason, "skipped": True}
        else:
            details["crit_event_before_end"] = {"ok": 1 if ok else 0, "reason": reason}

        ok, reason = check_crit_invoice_before_end(conn, cname, cend)
        if ok is None:
            details["crit_invoice_before_end"] = {"ok": 1, "reason": reason, "skipped": True}
        else:
            details["crit_invoice_before_end"] = {"ok": 1 if ok else 0, "reason": reason}

        ok, reason = check_crit_no_unsigned_docs(conn, cname)
        details["crit_no_unsigned_docs"] = {"ok": 1 if ok else 0, "reason": reason}

        critical_bad = sum(
            1 for k in ["crit_event_quarter", "crit_event_before_end", "crit_invoice_before_end"]
            if details[k]["ok"] == 0
        )
        auxiliary_bad = sum(
            1 for k in ["crit_no_complaints", "crit_no_rejected_orders", "crit_no_unsigned_docs"]
            if details[k]["ok"] == 0
        )

        final_color = determine_color(critical_bad, auxiliary_bad)

        conn.execute("""
            INSERT INTO traffic_light_results
                (client_id, client_name, manager, contract_end, calc_date, period_label,
                 crit_event_quarter, crit_no_complaints, crit_no_rejected_orders,
                 crit_event_before_end, crit_invoice_before_end, crit_no_unsigned_docs,
                 critical_bad, auxiliary_bad, final_color)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cid, cname, str(manager) if manager else "", str(cend) if cend else "",
            now_str, period_label,
            details["crit_event_quarter"]["ok"],
            details["crit_no_complaints"]["ok"],
            details["crit_no_rejected_orders"]["ok"],
            details["crit_event_before_end"]["ok"],
            details["crit_invoice_before_end"]["ok"],
            details["crit_no_unsigned_docs"]["ok"],
            critical_bad, auxiliary_bad, final_color,
        ))

        for spec in CRITERIA_SPEC:
            d = details[spec["id"]]
            conn.execute("""
                INSERT INTO traffic_light_details
                    (client_name, calc_date, criterion_id, criterion_name, status, reasoning)
                VALUES (?,?,?,?,?,?)
            """, (cname, now_str, spec["id"], spec["name"], d["ok"], d["reason"]))

    conn.commit()
    conn.close()

    return {"total": len(clients), "period_label": period_label}


def determine_color(critical_bad, auxiliary_bad):
    if critical_bad >= 2:
        return COLOR_RED
    if (critical_bad >= 1 and auxiliary_bad >= 2) or auxiliary_bad >= 3:
        return COLOR_RED
    if critical_bad >= 1 or auxiliary_bad >= 2:
        return COLOR_YELLOW
    return COLOR_GREEN


def get_details_for_client(client_name):
    conn = get_conn()
    cur = conn.execute("""
        SELECT criterion_name, status, reasoning
        FROM traffic_light_details
        WHERE client_name = ?
        ORDER BY id
    """, (client_name,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_results_summary():
    conn = get_conn()
    cur = conn.execute("""
        SELECT final_color, COUNT(*) as cnt FROM traffic_light_results
        GROUP BY final_color
    """)
    summary = {row["final_color"]: row["cnt"] for row in cur.fetchall()}
    conn.close()
    return summary
