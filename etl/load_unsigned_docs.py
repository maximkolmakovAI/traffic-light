import pandas as pd
import re
from db.database import get_conn
from config import SOURCE_DIR

def load_unsigned_docs(upload_id, source=None, source_filename=None):
    path = source or (SOURCE_DIR / "Неподписанные документы.xls")
    if source_filename is None:
        source_filename = "Неподписанные документы.xls"
    df = pd.read_excel(path, engine="xlrd", header=None)
    print(f"  Unsigned docs: {len(df)} rows x {df.shape[1]} cols")

    conn = get_conn()
    cur = conn.cursor()
    loaded = 0

    for idx, row in df.iterrows():
        vals = [str(v).strip() if pd.notna(v) else "" for v in row]
        col0 = vals[0] if len(vals) > 0 else ""

        if not col0 or idx < 7:
            continue
        if any(kw in col0 for kw in ["Реализация", "План работы", "Документ", "Сотрудник"]):
            continue
        if ";" in col0:
            continue

        pure = col0.replace(" ", "").replace("\xa0", "").replace(".", "").replace(",", "")
        if pure.replace("-", "").isdigit():
            continue

        has_pct = False
        for j in range(1, min(31, len(vals)), 2):
            if j < len(vals):
                v = str(vals[j]) if pd.notna(vals[j]) else ""
                if "%" in v or v.replace(",", "").replace(" ", "").replace(".", "").isdigit():
                    has_pct = True
                    break

        if has_pct:
            continue

        if any(kw in col0.upper() for kw in ["ООО", "ИП", "ЗАО", "АО ", "АНО", "ОАО"]):
            cur.execute("""
                INSERT INTO unsigned_docs (client_name, doc_status, upload_id, source_filename)
                VALUES (?, ?, ?, ?)
            """, (col0, "unsigned", upload_id, source_filename))
            loaded += 1
            continue

        if len(col0) > 5 and col0[0].isupper() and any(c.isupper() for c in col0[1:]):
            if "от " not in col0 and "№" not in col0:
                has_name_markers = sum(1 for kw in ["ый", "ая", "ое", "ие", "ск", "ов ", "ев ", "ин "] if kw in col0.lower())
                if has_name_markers == 0:
                    continue
                cur.execute("""
                    INSERT INTO unsigned_docs (client_name, doc_status, upload_id, source_filename)
                    VALUES (?, ?, ?, ?)
                """, (col0, "unsigned", upload_id, source_filename))
                loaded += 1

    conn.commit()
    conn.close()
    print(f"  Loaded {loaded} unsigned docs entries")
    return loaded
