import re

FILE_RULES = [
    (re.compile(r"список\s*клиентов", re.IGNORECASE), "clients", None, "Список клиентов"),
    (re.compile(r"события[_\s]февраль", re.IGNORECASE), "events", "февраль", "События февраль"),
    (re.compile(r"соыбтия[_\s]март", re.IGNORECASE), "events", "март", "События март"),
    (re.compile(r"события[_\s]март", re.IGNORECASE), "events", "март", "События март"),
    (re.compile(r"события[_\s]апрель", re.IGNORECASE), "events", "апрель", "События апрель"),
    (re.compile(r"жалоб", re.IGNORECASE), "complaints", None, "Жалобы"),
    (re.compile(r"(наряд|отсутсвие\s*нарядов|отклонен\s*клиентом)", re.IGNORECASE), "orders", None, "Наряды (отклонен клиентом)"),
    (re.compile(r"неподписанн", re.IGNORECASE), "unsigned_docs", None, "Неподписанные документы"),
    (re.compile(r"счет[аы]\s*на\s*продлен", re.IGNORECASE), "invoices", None, "Счета на продление"),
    (re.compile(r"ликвидац", re.IGNORECASE), "liquidation", None, "Ликвидация"),
]

STRUCTURE_RULES = {
    "clients": {"min_cols": 8, "keywords": ["контрагент", "инн", "окончание"]},
    "events": {"min_cols": 8, "keywords": ["окончание", "завершенное", "запланированное"]},
    "complaints": {"min_cols": 10, "keywords": ["жалоб", "контрагент"]},
    "orders": {"min_cols": 3, "keywords": ["контрагент", "статус наряда"]},
    "unsigned_docs": {"min_cols": 10, "keywords": ["реализация", "подразделение"]},
    "invoices": {"min_cols": 5, "keywords": ["счет", "сумма", "продл"]},
    "liquidation": {"min_cols": 2, "keywords": ["инн", "ликвидац"]},
}


def detect_by_filename(filename):
    for pattern, file_type, period, label in FILE_RULES:
        if pattern.search(filename):
            return {
                "file_type": file_type,
                "period": period,
                "label": label,
                "method": "filename",
            }
    return None


def detect_by_structure(file_buffer, filename=""):
    import pandas as pd

    try:
        if filename.endswith(".xlsx"):
            df = pd.read_excel(file_buffer, engine="openpyxl", nrows=5)
        else:
            df = pd.read_excel(file_buffer, engine="xlrd", nrows=5)
    except Exception as e:
        return {"file_type": "unknown", "period": None, "label": "Неизвестный", "method": "error", "error": str(e)}

    if df.empty:
        return {"file_type": "unknown", "period": None, "label": "Неизвестный", "method": "failed"}

    text = " ".join(str(c).lower() for c in df.columns if pd.notna(c)) + " "
    text += " ".join(str(v).lower() for _, row in df.iterrows() for v in row if pd.notna(v))

    for ftype, rules in STRUCTURE_RULES.items():
        if all(kw.lower() in text for kw in rules["keywords"]):
            if df.shape[1] >= rules["min_cols"]:
                for pattern, ft, period, label in FILE_RULES:
                    if ft == ftype:
                        return {
                            "file_type": ftype,
                            "period": period,
                            "label": label,
                            "method": "structure",
                        }
    return {"file_type": "unknown", "period": None, "label": "Неизвестный", "method": "failed"}


def detect_file_type(filename, file_buffer=None):
    result = detect_by_filename(filename)
    if result:
        return result
    if file_buffer:
        file_buffer.seek(0)
        return detect_by_structure(file_buffer, filename)
    return {"file_type": "unknown", "period": None, "label": "Неизвестный", "method": "failed"}
