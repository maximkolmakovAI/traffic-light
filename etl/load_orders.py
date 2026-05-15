import pandas as pd
from db.database import get_conn
from config import SOURCE_DIR

def load_orders(upload_id, source=None, source_filename=None):
    path = source or (SOURCE_DIR / "Отсутсвие нарядов на СИ со статусом отклонен клиентом (3 мес).xls")
    if source_filename is None:
        source_filename = "Отсутсвие нарядов на СИ со статусом отклонен клиентом (3 мес).xls"
    df = pd.read_excel(path, engine="xlrd", header=None)
    print(f"  Orders: {len(df)} rows x {df.shape[1]} cols")

    conn = get_conn()
    cur = conn.cursor()
    loaded = 0
    current_date = None

    for idx, row in df.iterrows():
        vals = [str(v).strip() if pd.notna(v) else "" for v in row]
        col0 = vals[0] if len(vals) > 0 else ""

        if not col0 or col0 in ("Дата", "Контрагент", "Исполнитель", "Ответственный", "Статус наряда"):
            continue

        if len(col0) == 10 and col0[2] == "." and col0[5] == ".":
            current_date = col0
            continue

        if len(vals) >= 4:
            client = col0
            if client and client not in ("", "nan", "None"):
                status = vals[3] if len(vals) > 3 else ""
                cur.execute("""
                    INSERT INTO rejected_orders (client_name, order_date, executor,
                                                  responsible, order_status, upload_id, source_filename)
                    VALUES (?,?,?,?,?,?,?)
                """, (client, current_date, vals[1] if len(vals) > 1 else "",
                      vals[2] if len(vals) > 2 else "", status, upload_id, source_filename))
                loaded += 1

    conn.commit()
    conn.close()
    print(f"  Loaded {loaded} orders")
    return loaded
