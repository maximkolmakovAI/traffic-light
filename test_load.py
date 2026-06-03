import sys; sys.path.insert(0, r'C:\AI_ALL\Разработка 1С на OpenCode\Анализ отчетов для Вали\traffic_light')
import streamlit as st
from app import load_traffic_data
result, crit_cols, details_map = load_traffic_data()
print(f'Result shape: {result.shape}')
print(f'Columns: {list(result.columns)}')
print(f'Distinct clients: {result["Клиент"].nunique()}')
print(f'Color counts:')
print(result['_color'].value_counts().to_dict())
print(f'First 3 clients: {result["Клиент"].head(3).tolist()}')
