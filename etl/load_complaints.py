import pandas as pd
from db.database import get_conn
from config import SOURCE_DIR

def load_complaints(upload_id, source=None, source_filename=None):
    path = source or (SOURCE_DIR / "Жалобы_февраль-апрель.xls")
    if source_filename is None:
        source_filename = "Жалобы_февраль-апрель.xls"
    df = pd.read_excel(path, engine="xlrd", header=None)
    print(f"  Complaints: {len(df)} rows x {df.shape[1]} cols")

    conn = get_conn()
    cur = conn.cursor()
    loaded = 0

    for idx, row in df.iterrows():
        vals = [str(v).strip() if pd.notna(v) else "" for v in row]
        col0 = vals[0] if len(vals) > 0 else ""

        if not col0:
            continue
        pure_num = col0.replace(" ", "").replace("\xa0", "")
        if not pure_num.isdigit():
            continue

        doc_number = vals[3] if len(vals) > 3 and vals[3] not in ("", "nan", "None") else ""
        employee = vals[4] if len(vals) > 4 and vals[4] not in ("", "nan", "None") else ""
        client_name = vals[7] if len(vals) > 7 and vals[7] not in ("", "nan", "None") else ""
        status = vals[12] if len(vals) > 12 and vals[12] not in ("", "nan", "None") else ""

        if client_name:
            cur.execute("""
                INSERT INTO complaints (client_name, doc_number, employee, status, upload_id, source_filename)
                VALUES (?,?,?,?,?,?)
            """, (client_name, doc_number, employee, status, upload_id, source_filename))
            loaded += 1

    conn.commit()
    conn.close()
    print(f"  Loaded {loaded} complaints")
    return loaded
