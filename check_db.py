import sys; sys.path.insert(0, r'C:\AI_ALL\Разработка 1С на OpenCode\Анализ отчетов для Вали\traffic_light')
from config import DB_PATH
import sqlite3
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cnt = conn.execute('SELECT COUNT(*) as c FROM traffic_light_results').fetchone()
print(f'traffic_light_results: {cnt["c"]} rows')
dcnt = conn.execute('SELECT COUNT(*) as c FROM traffic_light_details').fetchone()
print(f'traffic_light_details: {dcnt["c"]} rows')
clients = conn.execute('SELECT COUNT(DISTINCT client_name) as c FROM traffic_light_results').fetchone()
print(f'Distinct clients: {clients["c"]}')
colors = conn.execute('SELECT final_color, COUNT(*) as cnt FROM traffic_light_results GROUP BY final_color').fetchall()
for r in colors:
    print(f'  {r["final_color"]}: {r["cnt"]}')
sample = conn.execute('SELECT client_name FROM traffic_light_results LIMIT 5').fetchall()
print('Sample:', [r["client_name"] for r in sample])
conn.close()
