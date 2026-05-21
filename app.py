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
UNIVERSE_QUOTES = {
    "marvel": [
        "Великая сила — великая ответственность. А у Валентины — великие клиенты! 🕸️",
        "Мстители собираются! Валентина, твоя база ждёт своего героя. 🦸‍♀️",
        "Валентина, ты — Железный человек среди менеджеров! 🤖",
        "С надеждой и упорством, как Капитан Америка, Валентина ведёт менеджеров в бой! 🛡️",
    ],
    "starwars": [
        "Да пребудет с тобой Сила, Валентина! Менеджеры ждут твоих указаний. ✨",
        "Валентина — наш джедай в мире клиентского сервиса 🪐",
        "Империя не ждёт! Валентина, пора запускать светофор! 🚀",
        "Ты — наша последняя надежда, Валентина! Менеджеры готовы к миссии. 🌟",
    ],
    "harrypotter": [
        "Валентина, ты — настоящая Гермиона: без тебя менеджеры как без палочки! 🪄",
        "После трёх чашек кофе Валентина видит даже дементоров в отчётах! ☕🦉",
        "Валентина, Минерва Макгонагалл отдыхает — ты ведёшь менеджеров твёрдой рукой! ⚡",
        "Орден Феникса вызывает Валентину! База клиентов ждёт сортировки как Распределяющая шляпа! 🎩",
    ],
}
uni = random.choice(["marvel", "starwars", "harrypotter"])
greeting = random.choice(UNIVERSE_QUOTES[uni])

# ── Backgrounds by time-of-day + color-filter theme ──
hour = datetime.now().hour
filter_color = st.session_state.get("_color_filter", None)
if filter_color == "green":
    bg_style = "background: linear-gradient(135deg, #a8e063 0%, #56ab2f 50%, #2d8a17 100%);"
elif filter_color == "yellow":
    bg_style = "background: linear-gradient(135deg, #f7971e 0%, #ffd200 50%, #e8a317 100%);"
elif filter_color == "red":
    bg_style = "background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 50%, #8b0000 100%);"
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

# Dark theme adjustments for night
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
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {{ gap:0.15rem; }}
    .cell-info {{ background:#f0f2f6; padding:0.5rem; border-radius:0.5rem; border-left:4px solid #1f77b4; color:#000 !important; }}
    .color-btn {{
        display:inline-block; padding:0.5rem 1rem; margin:0.2rem; border-radius:0.5rem;
        border:2px solid transparent; cursor:pointer; font-weight:bold; text-align:center;
        transition: all 0.2s; min-width:120px;
    }}
    .color-btn:hover {{ transform:scale(1.03); opacity:0.9; }}
    .color-btn.active {{ border-color:#333; box-shadow:0 0 8px rgba(0,0,0,0.3); }}
    .trend-up {{ color:#2ecc71; font-weight:bold; }}
    .trend-down {{ color:#e74c3c; font-weight:bold; }}
    .trend-same {{ color:#95a5a6; }}

    /* ── Mascot styles (pure CSS, no JS needed) ── */
    .mascot {{
        position: fixed;
        font-size: 64px;
        line-height: 1;
        z-index: 9999;
        pointer-events: none;
        user-select: none;
        filter: drop-shadow(0 3px 6px rgba(0,0,0,0.3));
        image-rendering: pixelated;
        animation: mascot-cycle 56s infinite ease-in-out;
    }}
    @keyframes mascot-cycle {{
        /* wandering */
        0%   {{ left:3%; top:82%; transform:scaleX(1) translateY(0); opacity:1; }}
        7%   {{ left:12%; top:72%; transform:scaleX(1) translateY(-2px); opacity:1; }}
        14%  {{ left:35%; top:60%; transform:scaleX(-1) translateY(0); opacity:1; }}
        21%  {{ left:58%; top:48%; transform:scaleX(-1) translateY(-2px); opacity:1; }}
        28%  {{ left:75%; top:55%; transform:scaleX(1) translateY(0); opacity:1; }}
        35%  {{ left:88%; top:32%; transform:scaleX(1) translateY(-2px); opacity:1; }}
        42%  {{ left:65%; top:18%; transform:scaleX(-1) translateY(0); opacity:1; }}
        49%  {{ left:40%; top:12%; transform:scaleX(-1) translateY(-1px); opacity:1; }}
        /* climb to filter block */
        56%  {{ left:18%; top:5%; transform:scaleX(1) translateY(0); opacity:1; }}
        /* rest on filter block */
        70%  {{ left:18%; top:5.5%; transform:scaleX(1) rotate(2deg); opacity:0.85; }}
        84%  {{ left:18%; top:5%; transform:scaleX(1) rotate(-2deg); opacity:0.8; }}
        /* wake and start wandering */
        91%  {{ left:8%; top:30%; transform:scaleX(-1) translateY(0); opacity:1; }}
        100% {{ left:3%; top:82%; transform:scaleX(1) translateY(0); opacity:1; }}
    }}
    .mascot:hover {{
        animation: mascot-surprise 0.6s ease;
        transform:scale(1.3) !important;
    }}
    @keyframes mascot-surprise {{
        0%   {{ transform:scale(1) rotate(0deg); }}
        25%  {{ transform:scale(1.4) rotate(-12deg); }}
        50%  {{ transform:scale(1.1) rotate(8deg); }}
        75%  {{ transform:scale(1.3) rotate(-5deg); }}
        100% {{ transform:scale(1) rotate(0deg); }}
    }}


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
    .css-1offfwp {{ padding:0.5rem !important; }}
    /* ── Table full-width + compact cells ── */
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
    /* narrow columns for short criteria names */
    [data-testid="stDataFrame"] th:nth-child(5),
    [data-testid="stDataFrame"] th:nth-child(8) {{
        max-width:55px !important; width:55px !important;
    }}
    [data-testid="stDataFrame"] td:nth-child(5),
    [data-testid="stDataFrame"] td:nth-child(8) {{
        max-width:55px !important; width:55px !important;
    }}
    [data-testid="stDataFrame"] th:nth-child(6),
    [data-testid="stDataFrame"] th:nth-child(7),
    [data-testid="stDataFrame"] th:nth-child(9),
    [data-testid="stDataFrame"] th:nth-child(10) {{
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
    /* Client name column gets more space */
    [data-testid="stDataFrame"] th:nth-child(2) {{ min-width:120px !important; }}
    [data-testid="stDataFrame"] td:nth-child(2) {{ min-width:120px !important; }}
    {dark_adjust}
</style>
""", unsafe_allow_html=True)

# Mascot: pure CSS pixel cat (no emoji encoding issues on Py3.14)
CAT_CHAR = chr(0x1F408)  # 🐈 full body cat
st.markdown(
    '<div class="mascot" id="mascot-cat">' + CAT_CHAR + '</div>',
    unsafe_allow_html=True,
)
# JS enhancement for idle detection (if script executes, overrides CSS positioning)
st.markdown("""
<script>
if (!window.__catInit) {
  window.__catInit = true;
  (function() {
    var cat = document.getElementById('mascot-cat');
    if (!cat) return;
    var idleTimer = null, isSleeping = false, dir = 1;
    function stopCSS() {
      cat.style.animation = 'none';
      cat.style.transition = 'all 1.8s cubic-bezier(0.34,1.56,0.64,1)';
    }
    function walk() {
      if (isSleeping) return;
      stopCSS();
      cat.style.left = (Math.random()*75+2)+'%';
      cat.style.top = (Math.random()*65+20)+'%';
      if (Math.random()>0.5) dir *= -1;
      cat.style.transform = 'scaleX('+dir+')';
      setTimeout(walk, 2500+Math.random()*2500);
    }
    function climb() {
      if (isSleeping) return;
      isSleeping = true;
      stopCSS();
      cat.style.transition = 'all 2.5s cubic-bezier(0.6,0,0.4,1)';
      cat.style.left = '45%'; cat.style.top = '75%'; cat.style.transform = 'scaleX(1)';
      setTimeout(function(){
        cat.style.left = '22%'; cat.style.top = '5%'; cat.style.transform = 'scaleX(1)';
        setTimeout(function(){
          cat.style.transition = 'all 0.8s ease';
          cat.style.opacity = '0.8';
          cat.textContent = String.fromCodePoint(0x1F634);
        },2500);
      },2500);
    }
    function wake() {
      if (!isSleeping) return;
      isSleeping = false;
      cat.textContent = String.fromCodePoint(0x1F408);
      cat.style.opacity = '1';
      cat.style.animation = '';
      cat.style.transition = 'all 0.6s cubic-bezier(0.34,1.56,0.64,1)';
      cat.style.left = (Math.random()*70+10)+'%';
      cat.style.top = (Math.random()*50+30)+'%';
      setTimeout(function(){ cat.style.animation = 'none'; walk(); }, 600);
    }
    function onAction() { if (isSleeping) wake(); clearTimeout(idleTimer); idleTimer = setTimeout(climb, 10000); }
    document.addEventListener('mousemove', onAction);
    document.addEventListener('click', onAction);
    document.addEventListener('scroll', onAction);
    setTimeout(walk, 1500);
    idleTimer = setTimeout(climb, 10000);
  })();
}
</script>
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
    color = fdf.iloc[idx]["_color"] if idx in fdf.index else "green"
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

# ── Universe greeting ──
st.markdown(
    f"<div class='greeting-card'>✨ <b>Валентина</b>, {greeting}</div>",
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
        # ── Color filter buttons ──
        col_g, col_y, col_r = st.columns(3)
        active_filter = filter_color

        def _click_filter(color):
            cur = st.session_state.get("_color_filter", None)
            st.session_state["_color_filter"] = None if cur == color else color
        for col, color, label, cnt in [
            (col_g, "green", "Зеленый", counts.get("green", 0)),
            (col_y, "yellow", "Желтый", counts.get("yellow", 0)),
            (col_r, "red", "Красный", counts.get("red", 0)),
        ]:
            is_active = active_filter == color
            bg = COLOR_HEX.get(color, "#ccc")
            txt = "#fff" if color == "red" else "#333"
            active_cls = "active" if is_active else ""
            col.markdown(
                f"<div class='color-btn {active_cls}' style='background:{bg};color:{txt}' "
                f"onclick='alert(\"streamlit filter\")'>{label}: {cnt}</div>",
                unsafe_allow_html=True,
            )
            if col.button(f"{label}: {cnt}", key=f"cf_{color}", use_container_width=True,
                          type="primary" if is_active else "secondary"):
                _click_filter(color)
                st.rerun()

        # ── Cache data ──
        if "_cache" not in st.session_state or st.session_state.pop("_refresh", False):
            cdf, ccrit, cdm = load_traffic_data()
            st.session_state["_cache"] = (cdf, ccrit, cdm)
        df, crit_cols, details_map = st.session_state["_cache"]

        if not df.empty:
            # ── Filters row ──
            flt1, flt2, flt3, flt4, flt5 = st.columns([2, 2, 2, 1, 1])

            with flt1:
                managers = ["Все"] + sorted(df["Менеджер"].unique().tolist())
                selected_manager = st.selectbox("Менеджер", managers, key="mgr_f", label_visibility="collapsed")
            with flt2:
                color_opts = ["Все", "green", "yellow", "red"]
                if active_filter:
                    color_opts = [active_filter]
                selected_color = st.selectbox("Зона", color_opts,
                    format_func=lambda x: COLOR_LABEL.get(x, "Все") if x != "Все" else "Все",
                    key="col_f", label_visibility="collapsed")
            with flt3:
                show_on_verge = st.checkbox("⚠️ На грани ухудшения", key="on_verge", label_visibility="collapsed")
                st.caption("На грани ухудшения")
            with flt4:
                show_improved = st.checkbox("🟢↑ Улучшились", key="show_improved", label_visibility="collapsed")
            with flt5:
                show_worsened = st.checkbox("🔴↓ Ухудшились", key="show_worsened", label_visibility="collapsed")

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

            # ── Trend filters ──
            if show_improved:
                fdf = fdf[fdf["Тренд"] == "🟢↑"]
            if show_worsened:
                fdf = fdf[fdf["Тренд"] == "🔴↓"]

            if selected_manager != "Все":
                fdf = fdf[fdf["Менеджер"] == selected_manager]
            if selected_color != "Все" and not active_filter:
                fdf = fdf[fdf["_color"] == selected_color]
            elif active_filter and selected_color == "Все":
                fdf = fdf[fdf["_color"] == active_filter]

            # ── Display columns with trend ──
            display_cols = ["Тренд", "Клиент", "Менеджер", "Окончание",
                            "Соб.1р/кв", "Жалобы", "Наряды", "Соб.2мес", "Счет", "Документы",
                            "Крит", "Вспом"]

            styled = fdf[display_cols].style.apply(lambda row: render_color_row(row, fdf), axis=1)

            st.dataframe(styled, use_container_width=True, height=560)

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
