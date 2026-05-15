import pandas as pd
from db.database import get_conn
from config import SOURCE_DIR

def parse_events_file(filepath, period, upload_id, source=None, source_filename=None):
    path = source or filepath
    if source_filename is None:
        fname = filepath
        if hasattr(fname, "name"):
            fname = fname.name
        source_filename = str(fname).split("\\")[-1].split("/")[-1]
    df = pd.read_excel(path, engine="xlrd", header=None)
    print(f"  Events {period}: {len(df)} rows x {df.shape[1]} cols")

    conn = get_conn()
    cur = conn.cursor()
    loaded = 0

    pending = {}

    for idx, row in df.iterrows():
        vals = [str(v).strip() if pd.notna(v) else "" for v in row]
        col0 = vals[0] if len(vals) > 0 else ""

        if not col0:
            continue
        if "Параметры:" in col0 or "Вид сопровождения" in col0:
            continue
        if "Головной контрагент" in col0 or "№ п/п" in col0:
            continue
        if col0.strip() in ("Да", "Нет"):
            continue

        if "23:59:59" in col0:
            pending = {
                "contract_end": col0,
                "master_client": vals[3] if len(vals) > 3 and vals[3] not in ("", "nan", "None") else "",
                "event_completed": vals[5] if len(vals) > 5 else "",
                "event_planned": vals[6] if len(vals) > 6 else "",
                "has_completed": vals[7] if len(vals) > 7 else "",
                "has_planned": vals[8] if len(vals) > 8 else "",
                "has_completed_or_postponed": vals[9] if len(vals) > 9 else "",
                "has_planned_after": vals[10] if len(vals) > 10 else "",
            }
            continue

        pure_num = col0.replace(" ", "").replace("\xa0", "")
        if pure_num.isdigit() and pending:
            client_name = vals[3] if len(vals) > 3 and vals[3] not in ("", "nan", "None") else pending["master_client"]
            responsible = vals[5] if len(vals) > 5 and vals[5] not in ("", "nan", "None") else ""

            if client_name:
                cur.execute("""
                    INSERT INTO events (client_name, contract_end_date,
                        event_completed, event_planned,
                        has_completed, has_planned,
                        has_completed_or_postponed, has_planned_after,
                        responsible, period, upload_id, source_filename)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    client_name,
                    pending["contract_end"],
                    pending["event_completed"],
                    pending["event_planned"],
                    pending["has_completed"],
                    pending["has_planned"],
                    pending["has_completed_or_postponed"],
                    pending["has_planned_after"],
                    responsible,
                    period,
                    upload_id,
                    source_filename,
                ))
                loaded += 1
            pending = {}

    conn.commit()
    conn.close()
    print(f"  Loaded {loaded} events for {period}")
    return loaded


def load_events(upload_id_base):
    files = [
        (SOURCE_DIR / "События_февраль.xls", "февраль"),
        (SOURCE_DIR / "Соыбтия_март.xls", "март"),
        (SOURCE_DIR / "События_апрель.xls", "апрель"),
    ]
    total = 0
    for path, period in files:
        try:
            cnt = parse_events_file(path, period, upload_id_base)
            total += cnt
        except Exception as e:
            print(f"  Error loading {period}: {e}")
    return total

def load_events_from_file(source, period, upload_id, source_filename=None):
    return parse_events_file(None, period, upload_id, source=source, source_filename=source_filename)
