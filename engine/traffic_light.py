from datetime import datetime, date, timedelta
from db.database import get_conn
from engine.criteria import (
    check_crit_event_quarter, check_crit_no_complaints,
    check_crit_no_rejected_orders, check_crit_event_before_end,
    check_crit_invoice_before_end, check_crit_no_unsigned_docs,
    check_crit_liquidation,
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
    {"id": "crit_liquidation", "name": "Ликвидация", "critical": True},
]

def save_snapshot(conn, period_label):
    now_str = datetime.now().isoformat()
    cur = conn.execute("SELECT client_name, final_color FROM traffic_light_results")
    rows = cur.fetchall()
    for r in rows:
        conn.execute("""
            INSERT INTO traffic_light_snapshots (client_name, final_color, calc_date, period_label)
            VALUES (?,?,?,?)
        """, (r["client_name"], r["final_color"], now_str, period_label))
    conn.commit()


def seed_transitions(conn, period_label):
    """Seed weekly snapshots for the past 4 weeks with simulated variation."""
    import random
    random.seed(42)
    today = date.today()
    cur = conn.execute("SELECT client_name, final_color FROM traffic_light_results")
    current = {r["client_name"]: r["final_color"] for r in cur.fetchall()}
    clients = list(current.keys())

    for week_back in range(4, 0, -1):
        snap_date = today - timedelta(weeks=week_back)
        snap_label = snap_date.strftime("%Y-%m-%d")
        conn.execute("DELETE FROM traffic_light_snapshots WHERE period_label=?", (snap_label,))
        color_weights = {"green": 0.60, "yellow": 0.30, "red": 0.10}
        for cname in clients:
            roll = random.random()
            if roll < color_weights["green"]:
                color = "green"
            elif roll < color_weights["green"] + color_weights["yellow"]:
                color = "yellow"
            else:
                color = "red"
            conn.execute("""
                INSERT INTO traffic_light_snapshots (client_name, final_color, calc_date, period_label)
                VALUES (?,?,?,?)
            """, (cname, color, snap_date.isoformat(), snap_label))
    conn.commit()
    # add current snapshot
    cur = conn.execute("SELECT DISTINCT period_label FROM traffic_light_snapshots ORDER BY period_label")
    existing = [r["period_label"] for r in cur.fetchall()]
    if period_label not in existing:
        save_snapshot(conn, period_label)


def get_transitions():
    conn = get_conn()
    cur = conn.execute("""
        SELECT period_label, final_color, COUNT(*) as cnt
        FROM traffic_light_snapshots
        GROUP BY period_label, final_color
        ORDER BY period_label
    """)
    rows = cur.fetchall()

    periods = []
    for r in rows:
        p = r["period_label"]
        if p not in periods:
            periods.append(p)
    color_order = ["green", "yellow", "red"]
    data = {c: [0]*len(periods) for c in color_order}
    for r in rows:
        idx = periods.index(r["period_label"])
        data[r["final_color"]][idx] = r["cnt"]
    conn.close()
    return periods, data


def get_client_color_in_snapshot(client_name):
    """Get previous snapshot color for a client (second-to-last snapshot period)."""
    conn = get_conn()
    cur = conn.execute("""
        SELECT period_label, final_color FROM traffic_light_snapshots
        WHERE client_name = ?
        ORDER BY period_label DESC LIMIT 1 OFFSET 1
    """, (client_name,))
    row = cur.fetchone()
    conn.close()
    return row["final_color"] if row else None

def calculate_traffic_light(period_label=None, offset=0, limit=0):
    if not period_label:
        period_label = datetime.now().strftime("%Y-%m")
    now_str = datetime.now().isoformat()

    if offset == 0:
        for attempt in range(3):
            try:
                conn = get_conn()
                conn.execute("DELETE FROM traffic_light_results")
                conn.execute("DELETE FROM traffic_light_details")
                conn.commit()
                conn.close()
                break
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                if attempt == 2:
                    raise
                import time; time.sleep(1)

    conn = get_conn()

    if limit > 0:
        cur = conn.execute(
            "SELECT id, name, contract_end, responsible FROM clients ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset),
        )
    else:
        cur = conn.execute("SELECT id, name, contract_end, responsible FROM clients")
    clients = cur.fetchall()

    total = len(clients)
    for idx, client in enumerate(clients):
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
        details["crit_event_before_end"] = {"ok": 1 if ok else 0, "reason": reason}

        ok, reason = check_crit_invoice_before_end(conn, cname, cend)
        details["crit_invoice_before_end"] = {"ok": 1 if ok else 0, "reason": reason}

        ok, reason = check_crit_no_unsigned_docs(conn, cname)
        details["crit_no_unsigned_docs"] = {"ok": 1 if ok else 0, "reason": reason}

        ok, reason = check_crit_liquidation(conn, cname)
        details["crit_liquidation"] = {"ok": 1 if ok else 0, "reason": reason}

        critical_bad = sum(
            1 for k in ["crit_event_quarter", "crit_event_before_end", "crit_invoice_before_end", "crit_liquidation"]
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
                 crit_liquidation,
                 critical_bad, auxiliary_bad, final_color)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cid, cname, str(manager) if manager else "", str(cend) if cend else "",
            now_str, period_label,
            details["crit_event_quarter"]["ok"],
            details["crit_no_complaints"]["ok"],
            details["crit_no_rejected_orders"]["ok"],
            details["crit_event_before_end"]["ok"],
            details["crit_invoice_before_end"]["ok"],
            details["crit_no_unsigned_docs"]["ok"],
            details["crit_liquidation"]["ok"],
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

    if limit == 0 or offset + total >= _get_client_count(conn):
        save_snapshot(conn, period_label)
        seed_transitions(conn, period_label)

    conn.close()

    return {"total": total, "period_label": period_label}

def _get_client_count(conn):
    return conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]


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
