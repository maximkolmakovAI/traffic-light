import sys; sys.path.insert(0, r'C:\AI_ALL\Разработка 1С на OpenCode\Анализ отчетов для Вали\traffic_light')
from config import DB_PATH
import sqlite3
conn = sqlite3.connect(str(DB_PATH))
cols = conn.execute('PRAGMA table_info(traffic_light_results)').fetchall()
print('traffic_light_results columns:')
for c in cols:
    print(f'  {c[1]} ({c[2]})')
# Also check the raw data count
cnt_all = conn.execute('SELECT COUNT(*) FROM traffic_light_results').fetchone()[0]
print(f'Total rows: {cnt_all}')
conn.close()
