import pandas as pd
from datetime import datetime
from db.database import get_conn


def load_liquidation(upload_id, source=None, source_filename=None):
    if source_filename is None:
        source_filename = "ликвидация.xlsx"
    df = pd.read_excel(source, engine="openpyxl")
    df.columns = df.columns.str.strip()
    print(f"  Liquidation file: {len(df)} rows, columns: {list(df.columns)}")

    conn = get_conn()
    cur = conn.cursor()
    loaded = 0
    now = datetime.now().isoformat()

    for _, row in df.iterrows():
        inn = str(row.get("ИНН", row.get("inn", ""))).strip()
        if not inn or inn in ("", "nan", "None"):
            continue
        status = str(row.get("Статус", row.get("status", "unknown"))).strip()
        liq_date = str(row.get("Дата ликвидации", row.get("liquidation_date", ""))).strip()
        client_name = str(row.get("Контрагент", row.get("client_name", ""))).strip()

        if liq_date in ("", "nan", "None"):
            liq_date = ""

        cur.execute("""
            INSERT INTO liquidation_data
                (client_name, inn, liquidation_status, liquidation_date, check_date, source, upload_id, source_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (client_name, inn, status, liq_date, now, "file_upload", upload_id, source_filename))
        loaded += 1

    conn.commit()
    conn.close()
    print(f"  Loaded {loaded} liquidation entries")
    return loaded
