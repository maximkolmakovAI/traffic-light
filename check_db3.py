import sys; sys.path.insert(0, r'C:\AI_ALL\Разработка 1С на OpenCode\Анализ отчетов для Вали\traffic_light')
from config import DB_PATH
import sqlite3
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT final_color, COUNT(*) as cnt FROM traffic_light_results GROUP BY final_color').fetchall()
for r in rows:
    fc = r['final_color']
    c = r['cnt']
    print(f'  {fc}: {c}')
total = sum(r['cnt'] for r in rows)
print(f'Total: {total}')
conn.close()
