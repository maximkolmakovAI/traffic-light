import streamlit as st
import pandas as pd
import plotly.express as px
import io
import threading
import time
from pathlib import Path
from datetime import datetime, date

from db.database import init_db, get_conn
from db.seed import seed_demo_data
from etl.loader import run_all_etl
from etl.single_load import load_file_by_buffer, load_file_by_path, check_conflicts, resolve_conflicts
from engine.traffic_light import calculate_traffic_light, get_results_summary, get_details_for_client, get_transitions, get_client_color_in_snapshot

st.set_page_config(page_title="Светофор по клиентам", page_icon="🚦", layout="wide")

COLOR_LABEL = {"green": "Зеленый", "yellow": "Желтый", "red": "Красный"}
COLOR_BG = {"green": "#d4edda", "yellow": "#fff3cd", "red": "#f8d7da"}
COLOR_HEX = {"green": "#2ecc71", "yellow": "#f1c40f", "red": "#e74c3c"}

# ── Universe greeting ──
import random
random.seed(int(datetime.now().timestamp()) % 1000)
NAME_VARIANTS = ["Валя", "Валентина", "Леди Валентина", "Валентина фон Рук"]
_NAME = random.choice(NAME_VARIANTS)
UNIVERSE_QUOTES = {
    "marvel": [
        "Великая сила — великая ответственность. А у {n} — великие клиенты! \U0001F578\uFE0F",
        "Мстители собираются! {n}, твоя база ждёт своего героя. \U0001F9B8\u200D\u2640\uFE0F",
        "{n} — Железный человек среди менеджеров! \U0001F916",
        "С надеждой и упорством, как Капитан Америка, {n} ведёт менеджеров в бой! \U0001F6E1\uFE0F",
    ],
    "starwars": [
        "Да пребудет с тобой Сила, {n}! Менеджеры ждут твоих указаний. \u2728",
        "{n} — наш джедай в мире клиентского сервиса \U0001FABC",
        "Империя не ждёт! {n}, пора запускать светофор! \U0001F680",
        "Ты — наша последняя надежда, {n}! Менеджеры готовы к миссии. \U0001F31F",
    ],
    "harrypotter": [
        "{n}, ты — настоящая Гермиона: без тебя менеджеры как без палочки! \U0001FA84",
        "После трёх чашек кофе {n} видит даже дементоров в отчётах! \u2615\u200D\U0001F409",
        "{n}, Минерва Макгонагалл отдыхает — ты ведёшь менеджеров твёрдой рукой! \u26A1",
        "Орден Феникса вызывает {n}! База клиентов ждёт сортировки как Распределяющая шляпа! \U0001FA99",
    ],
}
uni = random.choice(["marvel", "starwars", "harrypotter"])
greeting = random.choice(UNIVERSE_QUOTES[uni]).format(n=_NAME)

# ── Theme detection (read before any CSS) ──
theme = st.session_state.get("theme_sel", "Базовый режим")

# ── Common CSS (layout, table widths — always applied) ──
st.markdown(f"""
<style>
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {{ gap:0.15rem; }}
    .css-1offfwp {{ padding:0.5rem !important; }}
    .main > div {{ max-width:100% !important; padding-left:0.3rem !important; padding-right:0.3rem !important; }}
    .block-container {{ padding:0.5rem 0.3rem !important; max-width:100% !important; }}
    [data-testid="column"] > div > div > div > div > div > div[data-testid="stDataFrame"] > div {{
        width:100% !important;
    }}
    [data-testid="stDataFrame"] table {{
        width:100% !important; table-layout:fixed !important;
    }}
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {{
        padding:1px 3px !important; font-size:0.78rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }}
    [data-testid="stDataFrame"] th:nth-child(5),
    [data-testid="stDataFrame"] th:nth-child(8) {{
        max-width:55px !important; width:55px !important;
    }}
    [data-testid="stDataFrame"] td:nth-child(5),
    [data-testid="stDataFrame"] td:nth-child(8) {{
        max-width:55px !important; width:55px !important;
    }}
    [data-testid="stDataFrame"] th:nth-child(9),
    [data-testid="stDataFrame"] th:nth-child(10) {{
        max-width:30px !important; width:30px !important;
    }}
    [data-testid="stDataFrame"] td:nth-child(9),
    [data-testid="stDataFrame"] td:nth-child(10) {{
        max-width:30px !important; width:30px !important;
    }}
    [data-testid="stDataFrame"] th:nth-child(6),
    [data-testid="stDataFrame"] th:nth-child(7) {{
        max-width:40px !important; width:40px !important;
    }}
    [data-testid="stDataFrame"] td:nth-child(6),
    [data-testid="stDataFrame"] td:nth-child(7),
    [data-testid="stDataFrame"] td:nth-child(9),
    [data-testid="stDataFrame"] td:nth-child(10) {{
        max-width:40px !important; width:40px !important;
    }}
    [data-testid="stDataFrame"] th:nth-child(11),
    [data-testid="stDataFrame"] th:nth-child(12) {{
        max-width:35px !important; width:35px !important;
    }}
    [data-testid="stDataFrame"] td:nth-child(11),
    [data-testid="stDataFrame"] td:nth-child(12) {{
        max-width:35px !important; width:35px !important;
    }}
    [data-testid="stDataFrame"] th:nth-child(2) {{ min-width:120px !important; }}
    [data-testid="stDataFrame"] td:nth-child(2) {{ min-width:120px !important; }}
    div[data-testid*="cf_"] button[kind="primary"] {{
        font-weight:bold !important; transform:scale(1.03);
    }}
</style>
""", unsafe_allow_html=True)

# ── Theme-specific CSS ──
if theme == "Квантовое ядро":
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;400;500;600&family=JetBrains+Mono:wght@300;400;500&display=swap');

    .stApp {
        background: linear-gradient(135deg, #0b1325 0%, #172036 30%, #1F2937 60%, #0f1729 100%) !important;
        background-attachment: fixed !important;
        transition: background 0.5s ease;
    }

    .stApp::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background:
            radial-gradient(ellipse at 20% 40%, rgba(96,165,250,0.07) 0%, transparent 55%),
            radial-gradient(ellipse at 80% 20%, rgba(96,165,250,0.04) 0%, transparent 45%),
            radial-gradient(ellipse at 50% 80%, rgba(31,41,55,0.2) 0%, transparent 50%);
        pointer-events: none;
        z-index: -1;
    }

    .stApp, .stApp header, .stApp footer,
    h1, h2, h3, h4, h5, h6, .stMarkdown, p, li, span,
    .stSelectbox label, .stCheckbox label, .stMetric label,
    .st-bw, .st-c5, .st-db, .st-dc, .st-dg, .st-dh {
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
    }

    .st-bv, .st-bw { color: #9CA3AF !important; }
    .st-d5, .st-d6, .st-d7, .st-d8, .st-da { border-color: rgba(255,255,255,0.1) !important; }

    [data-testid="stDataFrame"], [data-testid="stDataFrame"] table,
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th,
    code, pre, .stTextInput input, .st-b7, .st-b8, .st-b9, .st-ba, .st-bb,
    .st-bc, .st-bd, .st-be, .st-bf, .st-bg, .st-bh, .st-bi, .st-bj,
    div[data-baseweb="select"] span {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11px !important;
    }
    [data-testid="stDataFrame"] th {
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        background: rgba(96,165,250,0.12) !important;
        color: #FFFFFF !important;
        border-bottom: 1px solid rgba(255,255,255,0.08) !important;
        font-size: 0.72rem !important;
    }
    [data-testid="stDataFrame"] td {
        color: #E5E7EB !important;
        border-bottom: 1px solid rgba(255,255,255,0.04) !important;
    }
    [data-testid="stDataFrame"] { border-radius: 16px !important; overflow: hidden !important; }
    [data-testid="stDataFrame"] table { background: rgba(255,255,255,0.02) !important; }

    .greeting-card {
        background: linear-gradient(135deg, rgba(96,165,250,0.10) 0%, rgba(31,41,55,0.20) 100%) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 16px !important;
        box-shadow:
            rgba(255,255,255,0.04) 0px 1px 0px 0px inset,
            rgba(0,0,0,0.5) 0px 4px 16px 0px,
            rgba(96,165,250,0.06) 0px 0px 30px !important;
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
    }

    .stButton button, div[data-testid*="stButton"] button,
    .stDownloadButton button {
        border-radius: 16px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 400 !important;
        transition: all 0.15s ease !important;
    }
    .stButton button[kind="secondary"],
    .stDownloadButton button {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        color: #FFFFFF !important;
    }
    .stButton button[kind="secondary"]:hover,
    .stDownloadButton button:hover {
        background: rgba(255,255,255,0.08) !important;
        border-color: rgba(255,255,255,0.25) !important;
    }
    .stButton button[kind="primary"] {
        background: rgba(96,165,250,0.15) !important;
        border: 1px solid rgba(96,165,250,0.35) !important;
        color: #FFFFFF !important;
    }
    .stButton button[kind="primary"]:hover {
        background: rgba(96,165,250,0.25) !important;
    }

    div[data-testid*="cf_green"] button {
        background: rgba(46,204,113,0.12) !important;
        border: 1px solid rgba(46,204,113,0.25) !important;
        color: #4ade80 !important;
    }
    div[data-testid*="cf_green"] button[kind="primary"] {
        background: rgba(46,204,113,0.25) !important;
        border: 1px solid #4ade80 !important;
        color: #FFFFFF !important;
    }
    div[data-testid*="cf_yellow"] button {
        background: rgba(241,196,15,0.12) !important;
        border: 1px solid rgba(241,196,15,0.25) !important;
        color: #fbbf24 !important;
    }
    div[data-testid*="cf_yellow"] button[kind="primary"] {
        background: rgba(241,196,15,0.25) !important;
        border: 1px solid #fbbf24 !important;
        color: #FFFFFF !important;
    }
    div[data-testid*="cf_red"] button {
        background: rgba(231,76,60,0.12) !important;
        border: 1px solid rgba(231,76,60,0.25) !important;
        color: #f87171 !important;
    }
    div[data-testid*="cf_red"] button[kind="primary"] {
        background: rgba(231,76,60,0.25) !important;
        border: 1px solid #f87171 !important;
        color: #FFFFFF !important;
    }

    div[data-baseweb="select"], div[data-baseweb="select"] > div {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 12px !important;
        color: #FFFFFF !important;
    }
    div[data-baseweb="select"]:hover {
        border-color: rgba(96,165,250,0.4) !important;
    }
    .stSelectbox svg { fill: #FFFFFF !important; }

    div[data-testid="stRadio"] label {
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] {
        background: rgba(255,255,255,0.03) !important;
        border-radius: 12px !important;
        padding: 2px !important;
    }
    div[data-testid="stRadio"] div[data-testid="stMarkdownContainer"] p { color: #FFFFFF !important; }

    div[data-testid="stCheckbox"] label {
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
    }
    div[data-testid="stCheckbox"] svg { fill: #60A5FA !important; }

    .chat-user { background: rgba(96,165,250,0.12) !important; color: #FFFFFF !important; border-radius: 12px !important; }
    .chat-ai { background: rgba(255,255,255,0.04) !important; color: #FFFFFF !important; border-radius: 12px !important; }

    .cell-info {
        background: rgba(96,165,250,0.06) !important;
        border-left: 4px solid #60A5FA !important;
        color: #FFFFFF !important;
        border-radius: 12px !important;
    }

    .trend-up { color: #4ade80 !important; font-weight: bold; }
    .trend-down { color: #f87171 !important; font-weight: bold; }
    .trend-same { color: #6B7280 !important; }

    .stPlotlyChart, .js-plotly-plot, .plot-container { background: transparent !important; }
    .main-svg { background: transparent !important; }
    .stPlotlyChart { border-radius: 16px !important; overflow: hidden !important; }

    .st-eb, .st-ea, .st-dz, .st-dy, .st-dx { border-color: rgba(255,255,255,0.08) !important; }

    .st-cx, .st-cy, .st-cz, .st-da, .st-d0, .st-d1, .st-d2, .st-d3, .st-d4 {
        background: rgba(255,255,255,0.02) !important;
    }

    .st-subheader, .stSubheader, .st-emotion-cache-18ni7ap { color: #FFFFFF !important; }

    .st-cq { background: rgba(255,255,255,0.03) !important; }

    div[data-testid="stPopover"] button {
        border-radius: 16px !important;
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        color: #FFFFFF !important;
    }
    div[data-testid="stPopover"] button:hover {
        background: rgba(255,255,255,0.08) !important;
    }

    .st-divider { border-color: rgba(255,255,255,0.08) !important; }

    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.03) !important;
        border-radius: 12px !important;
        gap: 2px !important;
        padding: 2px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px !important;
        color: #9CA3AF !important;
        font-family: 'Inter', sans-serif !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: rgba(96,165,250,0.15) !important;
        color: #FFFFFF !important;
    }

    .st-bb, .st-bc, .st-bd, .st-be, .st-bf { background: rgba(255,255,255,0.02) !important; }

    .stAlert { border-radius: 12px !important; }

    input, textarea, .stTextInput input {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 12px !important;
        color: #FFFFFF !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    input:focus, textarea:focus {
        border-color: #60A5FA !important;
        box-shadow: 0 0 0 2px rgba(96,165,250,0.15) !important;
    }

    .st-bh, .st-bi, .st-bj { color: #FFFFFF !important; }

    .stProgress > div > div { background: #60A5FA !important; }
    .stProgress > div { background: rgba(255,255,255,0.08) !important; border-radius: 8px !important; }

    .st-spinner { color: #60A5FA !important; }

    /* Tooltip / dropdown menu */
    div[data-baseweb="popover"] div {
        background: #1F2937 !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
    }
    div[data-baseweb="menu"] div[role="option"] {
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
    }
    div[data-baseweb="menu"] div[role="option"]:hover {
        background: rgba(96,165,250,0.1) !important;
    }
</style>
""", unsafe_allow_html=True)
else:
    # ── Backgrounds by time-of-day + color-filter theme ──
    hour = datetime.now().hour
    filter_color = st.session_state.get("col_f", "Все")
    if filter_color == "green":
        bg_style = """background: linear-gradient(135deg, rgba(46,204,113,0.12) 0%, rgba(39,174,96,0.08) 100%),
                             radial-gradient(circle at 20% 80%, rgba(46,204,113,0.06) 0%, transparent 50%),
                             radial-gradient(circle at 80% 20%, rgba(39,174,96,0.06) 0%, transparent 50%);"""
    elif filter_color == "yellow":
        bg_style = """background: linear-gradient(135deg, rgba(241,196,15,0.12) 0%, rgba(243,156,18,0.08) 100%),
                             radial-gradient(circle at 30% 70%, rgba(241,196,15,0.06) 0%, transparent 50%),
                             radial-gradient(circle at 70% 30%, rgba(243,156,18,0.06) 0%, transparent 50%);"""
    elif filter_color == "red":
        bg_style = """background: linear-gradient(135deg, rgba(231,76,60,0.12) 0%, rgba(192,57,43,0.08) 100%),
                             radial-gradient(circle at 40% 60%, rgba(231,76,60,0.06) 0%, transparent 50%),
                             radial-gradient(circle at 60% 40%, rgba(192,57,43,0.06) 0%, transparent 50%);"""
    elif 6 <= hour < 9:
        bg_style = "background: linear-gradient(135deg, #667eea 0%, #f093fb 50%, #f9d976 100%);"
        bg_time_str = "🌅 Рассвет"
    elif 9 <= hour < 18:
        bg_style = "background: linear-gradient(135deg, #e0eafc 0%, #cfdef3 100%);"
        bg_time_str = "☀️ День"
    elif 18 <= hour < 21:
        bg_style = "background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 50%, #fdfcfb 100%);"
        bg_time_str = "🌇 Закат"
    else:
        bg_style = "background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);"
        bg_time_str = "🌙 Ночь"

    dark_adjust = """
        .stApp, .stApp header, .stApp footer { color: #e0e0e0 !important; }
        .st-bw, .st-c5, .st-db, .st-dc, .st-dg, .st-dh { color: #e0e0e0 !important; }
        .stSelectbox label, .stCheckbox label, .stMetric label { color: #e0e0e0 !important; }
        h1, h2, h3, h4, h5, h6, .stMarkdown, p, li, span:not([class*="emoji"]) {
            color: #e0e0e0 !important;
        }
    """ if hour < 6 or hour >= 21 else ""

    st.markdown(f"""
<style>
    .stApp {{
        {bg_style}
        background-attachment: fixed;
        transition: background 0.8s ease;
    }}
    .chat-user {{ background-color:#e3f2fd; padding:0.3rem; margin:0.15rem 0; border-radius:0.3rem; color:#000 !important; }}
    .chat-ai {{ background-color:#f5f5f5; padding:0.3rem; margin:0.15rem 0; border-radius:0.3rem; color:#000 !important; }}
    .cell-info {{ background:#f0f2f6; padding:0.5rem; border-radius:0.5rem; border-left:4px solid #1f77b4; color:#000 !important; }}
    .trend-up {{ color:#2ecc71; font-weight:bold; }}
    .trend-down {{ color:#e74c3c; font-weight:bold; }}
    .trend-same {{ color:#95a5a6; }}

    .greeting-card {{
        background: rgba(255,255,255,0.15);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-radius: 1rem;
        padding: 0.8rem 1.2rem;
        margin-bottom: 0.5rem;
        border: 1px solid rgba(255,255,255,0.3);
        font-size: 0.95rem;
        text-align: center;
    }}
    div[data-testid*="cf_green"] button {{
        background-color:rgba(46,204,113,0.2) !important;
        border-color:#2ecc71 !important; color:#1a7a42 !important;
    }}
    div[data-testid*="cf_yellow"] button {{
        background-color:rgba(241,196,15,0.2) !important;
        border-color:#f1c40f !important; color:#8a6d00 !important;
    }}
    div[data-testid*="cf_red"] button {{
        background-color:rgba(231,76,60,0.2) !important;
        border-color:#e74c3c !important; color:#8a1a1a !important;
    }}
    {dark_adjust}
</style>
""", unsafe_allow_html=True)


def get_details_map():
    conn = get_conn()
    dm = {}
    cur = conn.execute("SELECT client_name, criterion_name, status, reasoning FROM traffic_light_details")
    for r in cur.fetchall():
        cn = r["client_name"]
        if cn not in dm:
            dm[cn] = {}
        dm[cn][r["criterion_name"]] = {"status": r["status"], "reasoning": r["reasoning"]}
    conn.close()
    return dm


def load_traffic_data():
    conn = get_conn()
    df = pd.read_sql("""
        SELECT t.client_name AS "Клиент",
               t.manager AS "Менеджер",
               t.contract_end AS "Окончание",
               t.crit_event_quarter, t.crit_no_complaints,
               t.crit_no_rejected_orders, t.crit_event_before_end,
               t.crit_invoice_before_end, t.crit_no_unsigned_docs,
               t.critical_bad AS "Крит",
               t.auxiliary_bad AS "Вспом",
               t.final_color AS "Цвет"
        FROM traffic_light_results t
        ORDER BY CASE t.final_color WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END, t.client_name
    """, conn)
    details_map = get_details_map()
    conn.close()

    crit_cols = {
        "Соб.1р/кв": ("crit_event_quarter", "Событие 1 раз в квартал"),
        "Жалобы": ("crit_no_complaints", "Отсутствие жалоб за 3 мес"),
        "Наряды": ("crit_no_rejected_orders", "Отсутствие нарядов (отклонен клиентом)"),
        "Соб.2мес": ("crit_event_before_end", "Событие за 2 мес до окончания"),
        "Счет": ("crit_invoice_before_end", "Счет на продление за 2 мес до окончания"),
        "Документы": ("crit_no_unsigned_docs", "Отсутствие неподписанных документов"),
    }

    rows = []
    for _, row in df.iterrows():
        r = {k: row[k] for k in ["Клиент", "Менеджер", "Окончание", "Крит", "Вспом", "Цвет"]}
        cname = row["Клиент"]
        for label, (col, cname_full) in crit_cols.items():
            status = row[col]
            tip = ""
            if cname in details_map and cname_full in details_map[cname]:
                tip = details_map[cname][cname_full]["reasoning"]
            icon = "✅" if status == 1 else "❌"
            short = tip[:55].replace(";", ",") if tip else ""
            r[label] = f"{icon} {short}".strip() if status == 0 else icon
        rows.append(r)

    result = pd.DataFrame(rows)
    result["_color"] = df["Цвет"].values
    result["_crit_bad"] = df["Крит"].values
    result["_aux_bad"] = df["Вспом"].values

    # ── Trend column ──
    trends = []
    for _, row in df.iterrows():
        prev = get_client_color_in_snapshot(row["Клиент"])
        cur_c = row["Цвет"]
        color_order = {"green": 0, "yellow": 1, "red": 2}
        if prev and prev in color_order and cur_c in color_order:
            if color_order[cur_c] < color_order[prev]:
                trends.append("🟢↑")  # improved
            elif color_order[cur_c] > color_order[prev]:
                trends.append("🔴↓")  # worsened
            else:
                trends.append("⚪→")  # same
        else:
            trends.append("")
    result["Тренд"] = trends

    return result, crit_cols, details_map


def render_color_row(row, fdf):
    idx = row.name if hasattr(row, "name") else 0
    try:
        color = fdf.at[idx, "_color"]
    except (KeyError, ValueError, IndexError):
        color = "green"
    bg = COLOR_BG.get(color, "#ffffff")
    return [f"background-color: {bg}"] * len(row)


def async_ai(user_msg, history_copy):
    try:
        from ai_assistant import ask_ai
        reply = ask_ai(user_msg, history_copy)
        st.session_state["_ai_reply_ready"] = reply
    except Exception as e:
        st.session_state["_ai_reply_ready"] = f"⚠️ Ошибка: {e}"


init_db()

st.title("🚦 Светофор по клиентской базе")

# ── Theme selector (top row) ──
th_col1, _ = st.columns([1.5, 9])
with th_col1:
    st.selectbox("", ["Базовый режим", "Квантовое ядро"], key="theme_sel")

# ── Universe greeting ──
st.markdown(
    f"<div class='greeting-card'>✨ {greeting}</div>",
    unsafe_allow_html=True,
)

# ── AI chat popover ──
with st.popover("💬 Чат с ИИ", use_container_width=True):
    st.caption("Спрашивайте о клиентах, критериях и результатах")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "_ai_reply_ready" in st.session_state and st.session_state["_ai_reply_ready"] is not None:
        reply = st.session_state["_ai_reply_ready"]
        st.session_state.chat_history.append({"role": "assistant", "content": reply,
                                              "timestamp": datetime.now().isoformat()})
        st.session_state["_ai_reply_ready"] = None
        st.session_state["_ai_busy"] = False

    for msg in st.session_state.chat_history[-6:]:
        role = msg["role"]
        icon = "🙋" if role == "user" else "🤖"
        st.markdown(f"<div class='chat-{role}'><small>{icon} {msg['content'][:300]}</small></div>",
                    unsafe_allow_html=True)

    if st.session_state.get("_ai_busy", False):
        st.markdown("<small>⏳ ИИ думает…</small>", unsafe_allow_html=True)

    user_input = st.chat_input("Задайте вопрос о данных…", key="ai_chat_popover")
    if user_input and not st.session_state.get("_ai_busy", False):
        st.session_state.chat_history.append({"role": "user", "content": user_input,
                                              "timestamp": datetime.now().isoformat()})
        st.session_state["_ai_busy"] = True
        st.session_state["_ai_reply_ready"] = None
        hist_copy = list(st.session_state.chat_history)
        t = threading.Thread(target=async_ai, args=(user_input, hist_copy), daemon=True)
        t.start()
        st.rerun()

tab_main, tab_upload_single, tab_upload_folder, tab_info = st.tabs([
    "📊 Светофор", "📂 Загрузить файл", "📁 Загрузить папку", "ℹ️ Описание"
])

with tab_upload_single:
    st.info("⚠️ **Недоступно в тестовой версии.**")
    uploaded_file = st.file_uploader("Выберите Excel-файл отчета", type=["xls", "xlsx"], key="single_upload")
    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        buf = io.BytesIO(file_bytes)
        from etl.file_detector import detect_file_type
        detection = detect_file_type(uploaded_file.name, buf)
        if detection["file_type"] == "unknown":
            st.error(f"Не удалось определить тип файла: {uploaded_file.name}")
        else:
            st.info(f"**{detection['label']}**")
            batch_id = int(datetime.now().timestamp())
            state_key = f"conflict_{uploaded_file.name}"
            if st.session_state.get(state_key) != "resolved":
                conflicts = check_conflicts(detection["file_type"], detection["period"])
                if conflicts:
                    st.warning("Конфликты")
                    for c in conflicts:
                        st.write(f"- {c['message']}")
                    ca, cb, cc = st.columns(3)
                    if ca.button("🔄 Перезаписать", key=f"ra_{uploaded_file.name}", use_container_width=True):
                        buf.seek(0)
                        result = load_file_by_buffer(buf, uploaded_file.name, batch_id, resolution="replace")
                        if result["success"]:
                            resolve_conflicts(detection["file_type"], detection["period"], "replace", batch_id)
                            st.success(f"Загружено {result['loaded']}")
                            st.session_state[state_key] = "resolved"
                            st.rerun()
                    if cb.button("⏭️ Пропустить", key=f"sk_{uploaded_file.name}", use_container_width=True):
                        st.session_state[state_key] = "resolved"
                        st.rerun()
                    if cc.button("❌ Отменить", key=f"cn_{uploaded_file.name}", use_container_width=True):
                        st.session_state[state_key] = "cancelled"
                        st.rerun()
                else:
                    buf.seek(0)
                    with st.spinner("Загрузка…"):
                        result = load_file_by_buffer(buf, uploaded_file.name, batch_id)
                    if result["success"]:
                        st.success(f"✅ {result['loaded']} записей")
                        st.session_state[state_key] = "resolved"
                    else:
                        st.error(f"Ошибка: {result.get('error','')}")

with tab_upload_folder:
    st.info("⚠️ **Недоступно в тестовой версии.**")
    folder_path = st.text_input("Путь к папке",
        value=str(Path(r"C:\AI_ALL\Разработка 1С на OpenCode\Анализ отчетов для Вали\Исходные отчеты")),
        key="folder_path_input")
    if st.button("📂 Загрузить всё", use_container_width=True):
        folder = Path(folder_path)
        if not folder.exists():
            st.error(f"Папка не найдена")
        else:
            batch_id = int(datetime.now().timestamp())
            results, errors = [], []
            pb = st.progress(0, text="Загрузка…")
            flist = []
            for ext in ["*.xls", "*.xlsx", "*.XLS", "*.XLSX"]:
                flist.extend(sorted(folder.glob(ext)))
            for i, fp in enumerate(flist):
                pb.progress((i + 1) / len(flist), text=f"Обработка: {fp.name}")
                r = load_file_by_path(fp, batch_id, resolution="replace")
                results.append(r)
                if not r["success"]:
                    errors.append(f"{fp.name}: {r.get('error','')}")
            pb.empty()
            sc = sum(1 for r in results if r.get("success"))
            td = sum(r.get("loaded", 0) for r in results if r.get("success"))
            st.success(f"✅ {sc}/{len(flist)} файлов, {td} записей")
            if errors:
                with st.expander("Ошибки"):
                    for e in errors:
                        st.write(f"- {e}")
            if sc > 0 and st.button("📊 Рассчитать светофор", use_container_width=True):
                with st.spinner("Расчет…"):
                    calculate_traffic_light()
                st.success("Готово!")
                st.rerun()

with tab_main:
    conn = get_conn()
    counts_data = conn.execute(
        "SELECT final_color, COUNT(*) as cnt FROM traffic_light_results GROUP BY final_color"
    ).fetchall()
    conn.close()
    counts = {"green": 0, "yellow": 0, "red": 0}
    for r in counts_data:
        counts[r["final_color"]] = r["cnt"]
    total = sum(counts.values())

    col1, col2 = st.columns(2)
    if col1.button("🔄 Полная загрузка (ETL)", use_container_width=True):
        with st.spinner("Загрузка…"):
            try:
                run_all_etl(clear_first=True)
            except Exception:
                seed_demo_data()
        with st.spinner("Расчет светофора…"):
            calculate_traffic_light()
        st.session_state["_refresh"] = True
        st.success("Готово!")
        st.rerun()

    if col2.button("📊 Пересчитать светофор", use_container_width=True):
        with st.spinner("Расчет…"):
            calculate_traffic_light()
        st.session_state["_refresh"] = True
        st.success("Готово!")
        st.rerun()

    if total > 0:
        # ── Color filter buttons (shortcuts that set selectbox) ──
        col_g, col_y, col_r = st.columns(3)
        # Sync button visual state with selectbox (in case dropdown was used)
        if st.session_state.get("cf_btn", "Все") != st.session_state.get("col_f", "Все"):
            st.session_state["cf_btn"] = st.session_state["col_f"]
        cur_btn = st.session_state.get("cf_btn", "Все")
        for col, color, label, cnt in [
            (col_g, "green", "Зеленый", counts.get("green", 0)),
            (col_y, "yellow", "Желтый", counts.get("yellow", 0)),
            (col_r, "red", "Красный", counts.get("red", 0)),
        ]:
            is_active = cur_btn == color
            if col.button(f"{'●' if is_active else '○'} {label}: {cnt}",
                          key=f"cf_{color}", use_container_width=True,
                          type="primary" if is_active else "secondary"):
                new_val = "Все" if is_active else color
                st.session_state["col_f"] = new_val
                st.session_state["cf_btn"] = new_val
                st.rerun()

        # ── Cache data ──
        if "_cache" not in st.session_state or st.session_state.pop("_refresh", False):
            cdf, ccrit, cdm = load_traffic_data()
            st.session_state["_cache"] = (cdf, ccrit, cdm)
        df, crit_cols, details_map = st.session_state["_cache"]

        if not df.empty:
            # ── Filters row ──
            flt1, flt2, flt3, flt4 = st.columns([2, 2, 2, 3])

            with flt1:
                managers = ["Все"] + sorted(df["Менеджер"].unique().tolist())
                selected_manager = st.selectbox("Менеджер", managers, key="mgr_f", label_visibility="collapsed")
            with flt2:
                selected_color = st.selectbox("Зона", ["Все", "green", "yellow", "red"],
                    format_func=lambda x: COLOR_LABEL.get(x, "Все") if x != "Все" else "Все",
                    key="col_f", label_visibility="collapsed")
            with flt3:
                show_on_verge = st.checkbox("⚠️ На грани ухудшения", key="on_verge")
            with flt4:
                if st.session_state.get("trend_f") not in ("all", "up", "down"):
                    st.session_state["trend_f"] = "all"
                trend_filter = st.radio("Тренд:", ["all", "up", "down"],
                    format_func=lambda x: {"all": "Все", "up": "🟢↑ Улучшились", "down": "🔴↓ Ухудшились"}[x],
                    horizontal=True, key="trend_f", label_visibility="collapsed")

            fdf = df.copy()

            # ── "На грани ухудшения" filter ──
            if show_on_verge:
                def is_on_verge(row):
                    crit = row["_crit_bad"]
                    aux = row["_aux_bad"]
                    color = row["_color"]
                    if color == "green":
                        return aux == 1
                    if color == "yellow":
                        return (crit >= 1 and aux == 1) or (crit == 0 and aux == 2)
                    return False
                fdf = fdf[fdf.apply(is_on_verge, axis=1)]

            # ── Trend filter ──
            if trend_filter == "up":
                fdf = fdf[fdf["Тренд"] == "🟢↑"]
            elif trend_filter == "down":
                fdf = fdf[fdf["Тренд"] == "🔴↓"]

            if selected_manager != "Все":
                fdf = fdf[fdf["Менеджер"] == selected_manager]
            if selected_color != "Все":
                fdf = fdf[fdf["_color"] == selected_color]

            # ── Display columns with trend ──
            display_cols = ["Тренд", "Клиент", "Менеджер", "Окончание",
                            "Соб.1р/кв", "Жалобы", "Наряды", "Соб.2мес", "Счет", "Документы",
                            "Крит", "Вспом"]

            styled = fdf[display_cols].style.apply(lambda row: render_color_row(row, fdf), axis=1)

            st.dataframe(styled, use_container_width=True, height=560,
                column_config={
                    "Соб.1р/кв": st.column_config.Column(width="small"),
                    "Соб.2мес": st.column_config.Column(width="small"),
                    "Счет": st.column_config.Column(width="small"),
                })

            # ── Manual client selector ──
            all_clients = sorted(fdf["Клиент"].unique().tolist())
            sel_client = st.selectbox("🔍 Выберите клиента:", [""] + all_clients, key="client_sel")

            # ── Criterion selector ──
            sel_crit_name = ""
            sel_reasoning = ""
            if sel_client:
                crit_list = sorted(crit_cols.keys())
                sel_col_key = st.selectbox("📌 Критерий:", [""] + crit_list, key="crit_sel",
                    format_func=lambda x: crit_cols.get(x, ("", x))[1] if x else "")
                if sel_col_key:
                    sel_crit_name = crit_cols[sel_col_key][1]
                    sel_reasoning = details_map.get(sel_client, {}).get(sel_crit_name, {}).get("reasoning", "")

            # ── Cell info panel ──
            if sel_client and sel_crit_name and sel_reasoning:
                st.markdown(
                    f"<div class='cell-info'><b>🔍 {sel_client} → {sel_crit_name}</b><br>"
                    f"<small>{sel_reasoning}</small></div>",
                    unsafe_allow_html=True,
                )
            elif sel_client and sel_crit_name and not sel_reasoning:
                st.markdown(
                    f"<div class='cell-info'><b>🔍 {sel_client} → {sel_crit_name}</b><br>"
                    f"<small>Нет детальных данных (пересчитайте светофор)</small></div>",
                    unsafe_allow_html=True,
                )

            # ── Client details below table ──
            if sel_client:
                st.divider()
                st.markdown(f"**📋 Детализация по клиенту: {sel_client}**")
                details = get_details_for_client(sel_client)
                if details:
                    det_cols = st.columns(3)
                    for i, d in enumerate(details):
                        icon = "✅" if d["status"] else "❌"
                        clr = "#2ecc71" if d["status"] else "#e74c3c"
                        det_cols[i % 3].markdown(
                            f"<span style='color:{clr}'><b>{icon} {d['criterion_name']}</b></span>  \n"
                            f"<small>{d['reasoning'][:200]}</small>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("Нет данных (светофор не пересчитан)")

            csv = fdf.to_csv(index=False).encode("utf-8-sig")
            st.download_button("⬇️ CSV", csv, "svetofor.csv", "text/csv", use_container_width=True)

            # ── Charts ──
            st.divider()
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                pie_fig = px.pie(
                    names=["Зеленый", "Желтый", "Красный"],
                    values=[counts.get("green", 0), counts.get("yellow", 0), counts.get("red", 0)],
                    color=["Зеленый", "Желтый", "Красный"],
                    color_discrete_map={"Зеленый": "#2ecc71", "Желтый": "#f1c40f", "Красный": "#e74c3c"},
                    title="Распределение по цветам", height=400,
                )
                pie_fig.update_traces(textinfo="label+percent+value")
                st.plotly_chart(pie_fig, use_container_width=True)

            with chart_col2:
                conn2 = get_conn()
                violation_data = []
                crit_query = [
                    ("Событие 1 раз в квартал", "crit_event_quarter"),
                    ("Жалобы (3 мес)", "crit_no_complaints"),
                    ("Наряды (отклонен)", "crit_no_rejected_orders"),
                    ("Событие за 2 мес", "crit_event_before_end"),
                    ("Счет на продление", "crit_invoice_before_end"),
                    ("Неподписанные док-ты", "crit_no_unsigned_docs"),
                ]
                for cname, ccol in crit_query:
                    cur = conn2.execute(f"SELECT COUNT(*) as cnt FROM traffic_light_results WHERE {ccol}=0")
                    cnt = cur.fetchone()["cnt"]
                    violation_data.append({"Критерий": cname, "Нарушений": cnt})
                conn2.close()

                vdf = pd.DataFrame(violation_data)
                bar_fig = px.bar(vdf, x="Критерий", y="Нарушений",
                                 title="Сколько клиентов нарушают критерий",
                                 color="Нарушений", color_continuous_scale="Reds",
                                 height=400)
                bar_fig.update_xaxes(tickangle=45)
                st.plotly_chart(bar_fig, use_container_width=True)

            # ── Transition chart ──
            st.divider()
            st.subheader("📈 Статистика переходов между категориями")
            periods, trans_data = get_transitions()
            if len(periods) >= 2:
                tdf = pd.DataFrame({
                    "Неделя": periods,
                    "🟢 Зеленый": trans_data["green"],
                    "🟡 Желтый": trans_data["yellow"],
                    "🔴 Красный": trans_data["red"],
                })
                trans_fig = px.line(tdf, x="Неделя",
                                    y=["🟢 Зеленый", "🟡 Желтый", "🔴 Красный"],
                                    title="Динамика по неделям",
                                    color_discrete_map={
                                        "🟢 Зеленый": "#2ecc71",
                                        "🟡 Желтый": "#f1c40f",
                                        "🔴 Красный": "#e74c3c",
                                    },
                                    markers=True, height=400)
                st.plotly_chart(trans_fig, use_container_width=True)

                # Transitions summary
                prev_period = periods[-2]
                cur_period = periods[-1]
                conn3 = get_conn()
                cur = conn3.execute("""
                    SELECT s1.final_color as prev_color, s2.final_color as cur_color, COUNT(*) as cnt
                    FROM traffic_light_snapshots s1
                    JOIN traffic_light_snapshots s2 ON s1.client_name = s2.client_name
                    WHERE s1.period_label = ? AND s2.period_label = ?
                    GROUP BY s1.final_color, s2.final_color
                """, (prev_period, cur_period))
                trans_rows = cur.fetchall()
                conn3.close()
                if trans_rows:
                    st.caption("Переходы за последнюю неделю:")
                    trans_info = []
                    for tr in trans_rows:
                        trans_info.append(f"{COLOR_LABEL.get(tr['prev_color'], '?')} → {COLOR_LABEL.get(tr['cur_color'], '?')}: {tr['cnt']}")
                    st.markdown(" | ".join(trans_info))
            else:
                st.info("Данные о переходах будут доступны после нескольких расчетов светофора.")
    else:
        st.info("Данные не загружены. Используйте вкладки загрузки.")

with tab_info:
    st.subheader("Критерии")
    st.markdown("""
| Критерий | Тип | Описание |
|----------|-----|----------|
| **Событие 1 раз в квартал** | 🔴 Критичный | Есть завершенное/перенесенное событие в любом из 3 месяцев |
| **Событие за 2 мес до окончания** | 🔴 Критичный | Есть событие (только для договоров с окончанием ≤ 67 дней) |
| **Счет на продление за 2 мес** | 🔴 Критичный | Выставлен счет (только для договоров с окончанием ≤ 67 дней) |
| **Отсутствие жалоб за 3 мес** | 🟡 Вспомогательный | Клиента нет в списке жалоб |
| **Отсутствие нарядов (отклонен)** | 🟡 Вспомогательный | Нет нарядов со статусом "Отклонен клиентом" |
| **Отсутствие неподписанных док-тов** | 🟡 Вспомогательный | Все документы подписаны или сданы в расчетный отдел |
    """)
    st.subheader("Правила")
    st.markdown("""
- 🟢 **Зеленый**: 0 критичных, < 2 вспомогательных
- 🟡 **Желтый**: 1+ критичных ИЛИ 2+ вспомогательных
- 🔴 **Красный**: 2+ критичных ИЛИ 1+ критичных + 2+ вспомогательных ИЛИ 3+ вспомогательных
    """)
