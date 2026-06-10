import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "traffic_light.db"

SOURCE_DIR = BASE_DIR / "data" / "source"

LIQUIDATION_CACHE_DAYS = 2  # re-check after 2 days

CRITERIA = [
    {"id": "crit_event_quarter", "name": "Событие 1 раз в квартал (завершенное или перенесенное)", "critical": True, "source": "events"},
    {"id": "crit_no_complaints", "name": "Отсутствие жалоб за (3 мес)", "critical": False, "source": "complaints"},
    {"id": "crit_no_rejected_orders", "name": "Отсутствие нарядов на СИ со статусом 'отклонен клиентом' (3 мес)", "critical": False, "source": "orders"},
    {"id": "crit_event_before_end", "name": "Событие за два месяца до окончания (завершенное или перенесенное)", "critical": True, "source": "events"},
    {"id": "crit_invoice_before_end", "name": "Счет на продление за два месяца до окончания", "critical": True, "source": "invoices"},
    {"id": "crit_no_unsigned_docs", "name": "Отсутствие неподписанных документов", "critical": False, "source": "unsigned_docs"},
    {"id": "crit_liquidation", "name": "Ликвидация", "critical": True, "source": "dadata"},
]

TRAFFIC_RULES = {
    "red": [
        "critical_bad >= 1 AND auxiliary_bad >= 2",
        "auxiliary_bad >= 3",
    ],
    "yellow": [
        "critical_bad >= 1",
        "auxiliary_bad >= 2",
    ],
}
