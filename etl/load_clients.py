import pandas as pd
from db.database import get_conn
from config import SOURCE_DIR

def load_clients(upload_id, source=None, source_filename=None):
    path = source or (SOURCE_DIR / "список клиентов.xlsx")
    if source_filename is None:
        source_filename = "список клиентов.xlsx"
    df = pd.read_excel(path, engine="openpyxl")
    df.columns = df.columns.str.strip()
    print(f"  Clients file: {len(df)} rows, columns: {list(df.columns)}")

    conn = get_conn()
    cur = conn.cursor()
    loaded = 0

    col_map = {
        "Контрагент": "name",
        "Контрагент.ИНН": "inn",
        "Начало": "contract_start",
        "Окончание": "contract_end",
        "Длительность": "duration",
        "Состояние": "status",
        "Вид сопровождения": "support_type",
        "Исполнитель": "executor",
        "Вар1.Ответственный": "responsible",
        "Ответственный за направление": "direction_responsible",
    }

    for _, row in df.iterrows():
        client_name = str(row.get("Контрагент", "")).strip()
        if not client_name or client_name in ("", "nan", "None"):
            continue

        inn_val = row.get("Контрагент.ИНН")
        if pd.notna(inn_val):
            inn_val = str(int(float(inn_val))) if isinstance(inn_val, (int, float)) else str(inn_val)
        else:
            inn_val = ""

        cur.execute("""
            INSERT OR IGNORE INTO clients
                (name, inn, contract_start, contract_end, duration, status,
                 support_type, executor, responsible, direction_responsible,
                 upload_id, source_filename)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            client_name,
            inn_val,
            str(row.get("Начало", "")) if pd.notna(row.get("Начало")) else "",
            str(row.get("Окончание", "")) if pd.notna(row.get("Окончание")) else "",
            int(row.get("Длительность", 0)) if pd.notna(row.get("Длительность")) else 0,
            str(row.get("Состояние", "")) if pd.notna(row.get("Состояние")) else "",
            str(row.get("Вид сопровождения", "")) if pd.notna(row.get("Вид сопровождения")) else "",
            str(row.get("Исполнитель", "")) if pd.notna(row.get("Исполнитель")) else "",
            str(row.get("Вар1.Ответственный", "")) if pd.notna(row.get("Вар1.Ответственный")) else "",
            str(row.get("Ответственный за направление", "")) if pd.notna(row.get("Ответственный за направление")) else "",
            upload_id,
            source_filename,
        ))
        loaded += 1

    conn.commit()
    conn.close()
    print(f"  Loaded {loaded} clients")
    return loaded
