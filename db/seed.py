import random
from datetime import datetime, timedelta
from db.database import get_conn
from engine.traffic_light import calculate_traffic_light

def seed_demo_data():
    conn = get_conn()
    cur = conn.cursor()

    for t in ["traffic_light_details", "traffic_light_results", "unsigned_docs",
              "renewal_invoices", "rejected_orders", "complaints", "events",
              "clients", "source_uploads"]:
        conn.execute(f"DELETE FROM {t}")

    managers = [
        "Иванов Иван Иванович", "Петрова Анна Сергеевна",
        "Сидоров Петр Алексеевич", "Козлова Елена Дмитриевна",
        "Новиков Михаил Андреевич", "Васильева Ольга Павловна",
    ]

    clients_data = [
        ("ООО "ТехноПром"", "7701234567", "01.01.2025", "31.12.2026", "1С:Комплект Поддержки"),
        ("ЗАО "СтройИнвест"", "7702345678", "01.03.2025", "28.02.2027", "1С:Комплект Поддержки"),
        ("АО "АльфаТрейд"", "7703456789", "01.06.2025", "31.05.2027", "1С:Фреш"),
        ("ООО "БетаЛогистик"", "7704567890", "01.02.2025", "31.01.2026", "1С:Комплект Поддержки"),
        ("ИП Смирнов А.В.", "7705678901", "01.04.2025", "31.03.2027", "1С:Комплект Поддержки"),
        ("ООО "ГаммаЭнерго"", "7706789012", "01.05.2025", "30.04.2027", "1С:Комплект Поддержки"),
        ("ЗАО "ДельтаСофт"", "7707890123", "01.07.2025", "30.06.2026", "1С:Комплект Поддержки"),
        ("ООО "ИпсилонМедиа"", "7708901234", "01.08.2025", "31.07.2027", "1С:Фреш"),
        ("АО "КаппаСтрой"", "7709012345", "01.09.2025", "31.08.2026", "1С:Комплект Поддержки"),
        ("ООО "ЛямбдаТек"", "7710123456", "01.10.2025", "30.09.2027", "1С:Комплект Поддержки"),
        ("ООО "МюКонсалт"", "7711234567", "01.11.2025", "31.10.2026", "1С:Комплект Поддержки"),
        ("ЗАО "НюСервис"", "7712345678", "01.12.2025", "30.11.2027", "1С:Фреш"),
        ("АО "ОмегаПро"", "7713456789", "01.01.2026", "31.12.2027", "1С:Комплект Поддержки"),
        ("ООО "ПиТехнологии"", "7714567890", "01.02.2026", "31.01.2028", "1С:Комплект Поддержки"),
        ("ЗАО "СигмаГрупп"", "7715678901", "01.03.2026", "28.02.2028", "1С:Комплект Поддержки"),
        ("ООО "ТауАвто"", "7716789012", "01.04.2026", "31.03.2028", "1С:Фреш"),
        ("ИП Федоров И.М.", "7717890123", "01.05.2026", "30.04.2028", "1С:Комплект Поддержки"),
        ("ООО "ФиАналитика"", "7718901234", "01.06.2025", "31.05.2027", "1С:Комплект Поддержки"),
        ("АО "ХиКапитал"", "7719012345", "01.07.2025", "30.06.2027", "1С:Комплект Поддержки"),
        ("ООО "ПсиЭксперт"", "7720123456", "01.08.2025", "31.07.2027", "1С:Фреш"),
    ]

    client_ids = []
    for i, (name, inn, start, end, stype) in enumerate(clients_data):
        mgr = random.choice(managers)
        cur.execute("""
            INSERT INTO clients (name, inn, contract_start, contract_end, duration,
                                 status, support_type, executor, responsible, direction_responsible,
                                 source_filename)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (name, inn, start, end, 24, "В работе", stype, mgr, mgr,
              random.choice(managers), "демо-данные"))
        client_ids.append(cur.lastrowid)

    conn.commit()

    months = ["февраль", "март", "апрель"]
    for client_id, (name, _, _, end, _) in enumerate(clients_data):
        client_name = clients_data[client_id][0]
        for month in months:
            has_event = random.random() > 0.35
            cur.execute("""
                INSERT INTO events (client_name, contract_end_date, has_completed_or_postponed,
                                    period, source_filename)
                VALUES (?,?,?,?,?)
            """, (client_name, end, "Да" if has_event else "Нет", month, "демо-данные"))

    complaint_clients = ["ООО "БетаЛогистик"", "ООО "МюКонсалт"", "АО "КаппаСтрой"", "ИП Смирнов А.В."]
    for cname in complaint_clients:
        cur.execute("""
            INSERT INTO complaints (client_name, doc_number, employee, status, source_filename)
            VALUES (?,?,?,?,?)
        """, (cname, f"Жалоба 017/{random.randint(100000,999999)} от {datetime.now():%d.%m.%Y}",
              random.choice(managers), "Рассмотрена", "демо-данные"))

    unsigned_clients = ["ООО "БетаЛогистик"", "ООО "МюКонсалт"", "АО "КаппаСтрой"",
                         "ООО "ТехноПром"", "ЗАО "СтройИнвест"", "ООО "ГаммаЭнерго"",
                         "ООО "ПиТехнологии"", "ЗАО "СигмаГрупп"", "АО "ХиКапитал""]
    for cname in unsigned_clients:
        cur.execute("""
            INSERT INTO unsigned_docs (client_name, doc_status, source_filename)
            VALUES (?,?,?)
        """, (cname, "unsigned", "демо-данные"))

    invoice_clients = ["ООО "ТехноПром"", "ЗАО "СтройИнвест"", "АО "АльфаТрейд"",
                        "ООО "ГаммаЭнерго"", "АО "ХиКапитал""]
    for cname in invoice_clients:
        cur.execute("""
            INSERT INTO renewal_invoices (client_name, manager, has_invoice, invoice_number, source_filename)
            VALUES (?,?,?,?,?)
        """, (cname, random.choice(managers), 1,
              f"Счет 017/{random.randint(100000,999999)} от {datetime.now():%d.%m.%Y}",
              "демо-данные"))

    conn.commit()
    conn.close()
    print("Demo data seeded successfully")
