import sys; sys.path.insert(0, r'C:\AI_ALL\Разработка 1С на OpenCode\Анализ отчетов для Вали\traffic_light')
import pandas as pd
from db.database import get_conn, clear_all_data
from engine.traffic_light import calculate_traffic_light

conn = get_conn()
cur = conn.execute('SELECT final_color, COUNT(*) as cnt FROM traffic_light_results GROUP BY final_color')
print('=== Git DB (as-is) ===')
rows = cur.fetchall()
for r in rows:
    fc = r['final_color']; c = r['cnt']
    print(f'  {fc}: {c}')
conn.close()

print()
print('=== Recalculate with today (June 3) ===')
conn = get_conn()
conn.execute('DELETE FROM traffic_light_results')
conn.execute('DELETE FROM traffic_light_details')
conn.commit()
conn.close()

calculate_traffic_light()

conn = get_conn()
cur = conn.execute('SELECT final_color, COUNT(*) as cnt FROM traffic_light_results GROUP BY final_color')
rows = cur.fetchall()
for r in rows:
    fc = r['final_color']; c = r['cnt']
    print(f'  {fc}: {c}')
total = conn.execute('SELECT COUNT(*) FROM traffic_light_results').fetchone()[0]
print(f'  Total: {total}')
conn.close()
