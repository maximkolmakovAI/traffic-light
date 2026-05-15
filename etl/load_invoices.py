import pandas as pd
import re
from db.database import get_conn
from config import SOURCE_DIR

def load_invoices(upload_id, source=None, source_filename=None):
    path = source or (SOURCE_DIR / "Счета на продление.xls")
    if source_filename is None:
        source_filename = "Счета на продление.xls"
    df = pd.read_excel(path, engine="xlrd", header=None)
    print(f"  Invoices: {len(df)} rows x {df.shape[1]} cols")

    conn = get_conn()
    cur = conn.cursor()
    loaded = 0
    current_manager = None
    client_pattern = re.compile(r'^(.+?)\s*\(1С:')

    for idx, row in df.iterrows():
        vals = [str(v).strip() if pd.notna(v) else "" for v in row]
        col0 = vals[0] if len(vals) > 0 else ""
        col5 = vals[5] if len(vals) > 5 else ""
        col7 = vals[7] if len(vals) > 7 else ""

        if not col0 and not col5:
            continue
        if "Параметры:" in col0 or "Вид сопровождения" in col0:
            continue
        if col0 in ("Да", "Нет") and col5 in ("", "nan", "None"):
            continue
        if "Подразделение" in col0 and len(vals) < 4:
            continue
        if "Группа ИТС" in col0 or col0 in ("", "nan", "None"):
            if not col0 and col5:
                col0 = col5
            elif not col5:
                continue

        pure_manager = col0.replace("Ответственный", "").strip()
        if pure_manager and " " in pure_manager and not "1С:" in pure_manager and not "(" in pure_manager:
            if col0.count(" ") >= 1 and len(col0) > 5 and col0.count(".") <= 2:
                current_manager = col0
                continue

        client_name = ""
        has_invoice = 0
        invoice_number = ""
        invoice_date = ""
        invoice_amount = ""

        for candidate in [col0, col5]:
            if not candidate or candidate in ("nan", "None", ""):
                continue
            m = client_pattern.search(candidate)
            if m:
                client_name = m.group(1).strip()
                break
            if "1С:" in candidate:
                parts = candidate.split(" (1С:")
                client_name = parts[0].strip()
                break

        if client_name and col7 and col7 not in ("nan", "None", ""):
            has_invoice = 1
            inv_parts = col7.replace(",", "").split()
            for p in inv_parts:
                if p.replace(".", "").replace(" ", "").isdigit():
                    invoice_amount = p
                    break

        if client_name:
            cur.execute("""
                INSERT INTO renewal_invoices (client_name, manager, has_invoice,
                                               invoice_number, invoice_amount, upload_id, source_filename)
                VALUES (?,?,?,?,?,?,?)
            """, (client_name, current_manager or "", has_invoice,
                  col7 if has_invoice else "", invoice_amount, upload_id, source_filename))
            loaded += 1

    conn.commit()
    conn.close()
    print(f"  Loaded {loaded} invoice entries")
    return loaded
