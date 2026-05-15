import streamlit as st
import pandas as pd
import plotly.express as px
import io
import threading
import time
from pathlib import Path
from datetime import datetime

from db.database import init_db, get_conn
from db.seed import seed_demo_data
from etl.loader import run_all_etl
from etl.single_load import load_file_by_buffer, load_file_by_path, check_conflicts, resolve_conflicts
from engine.traffic_light import calculate_traffic_light, get_results_summary, get_details_for_client
from ai_assistant import ask_ai

st.set_page_config(page_title="Светофор по клиентам", page_icon="🚦", layout="wide")

COLOR_LABEL = {"green": "Зеленый", "yellow": "Желтый", "red": "Красный"}
COLOR_SUBTLE = {"green": "#d4edda", "yellow": "#fff3cd", "red": "#f8d7da"}

st.markdown("""
<style>
    .chat-user { background-color:#e3f2fd; padding:0.3rem; margin:0.15rem 0; border-radius:0.3rem; }
    .chat-ai { background-color:#f5f5f5; padding:0.3rem; margin:0.15rem 0; border-radius:0.3rem; }
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] { gap:0.15rem; }
    .cell-info { background:#f0f2f6; padding:0.5rem; border-radius:0.5rem; border-left:4px solid #1f77b4; }
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
        "Неп.док": ("crit_no_unsigned_docs", "Отсутствие неподписанных документов"),
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
    return result, crit_cols, details_map


def render_color_row_2(row, fdf):
    idx = row.name if hasattr(row, "name") else 0
    color = fdf.iloc[idx]["_color"] if idx in fdf.index else "green"
    bg = COLOR_SUBTLE.get(color, "#ffffff")
    return [f"background-color: {bg}"] * len(row)


def _extract_selection(selection):
    """Extract (client_name, column_name) from st.dataframe selection."""
    try:
        sel = selection.selection if hasattr(selection, "selection") else selection
        sel_rows = sel.rows if hasattr(sel, "rows") else sel.get("rows", [])
        sel_cols = sel.columns if hasattr(sel, "columns") else sel.get("columns", [])
        return sel_rows, sel_cols
    except Exception:
        return [], []


def async_ai(user_msg, history_copy):
    try:
        reply = ask_ai(user_msg, history_copy)
        st.session_state["_ai_reply_ready"] = reply
    except Exception as e:
        st.session_state["_ai_reply_ready"] = f"⚠️ Ошибка: {e}"


init_db()

st.title("🚦 Светофор по клиентской базе")

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
        ma, mb, mc = st.columns(3)
        ma.metric("🟢 Зеленые", counts.get("green", 0), border=True)
        mb.metric("🟡 Желтые", counts.get("yellow", 0), border=True)
        mc.metric("🔴 Красные", counts.get("red", 0), border=True)

        # cache ALL data in session — refreshes only after ETL/recalc
        if "_cache" not in st.session_state or st.session_state.pop("_refresh", False):
            cdf, ccrit, cdm = load_traffic_data()
            st.session_state["_cache"] = (cdf, ccrit, cdm)
        df, crit_cols, details_map = st.session_state["_cache"]

        if not df.empty:
            flt1, flt2 = st.columns([1, 1])
            with flt1:
                managers = ["Все"] + sorted(df["Менеджер"].unique().tolist())
                selected_manager = st.selectbox("Менеджер", managers, key="mgr_f", label_visibility="collapsed")
            with flt2:
                color_opts = ["Все", "green", "yellow", "red"]
                selected_color = st.selectbox("Зона", color_opts,
                    format_func=lambda x: COLOR_LABEL.get(x, "Все") if x != "Все" else "Все",
                    key="col_f", label_visibility="collapsed")

            fdf = df.copy()
            if selected_manager != "Все":
                fdf = fdf[fdf["Менеджер"] == selected_manager]
            if selected_color != "Все":
                fdf = fdf[fdf["_color"] == selected_color]

            display_cols = ["Клиент", "Менеджер", "Окончание",
                            "Соб.1р/кв", "Жалобы", "Наряды", "Соб.2мес", "Счет", "Неп.док",
                            "Крит", "Вспом"]

            styled = fdf[display_cols].style.apply(lambda row: render_color_row_2(row, fdf), axis=1)

            # DataFrame (without on_select — стабильно, без зависаний)
            st.dataframe(styled, use_container_width=True, height=680)

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

            # ── Cell info panel (сразу под критерием) ──
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

            st.divider()
            pie_fig = px.pie(
                names=["Зеленый", "Желтый", "Красный"],
                values=[counts.get("green", 0), counts.get("yellow", 0), counts.get("red", 0)],
                color=["Зеленый", "Желтый", "Красный"],
                color_discrete_map={"Зеленый": "#2ecc71", "Желтый": "#f1c40f", "Красный": "#e74c3c"},
                title="Распределение", height=300,
            )
            pie_fig.update_traces(textinfo="label+percent+value")
            st.plotly_chart(pie_fig, use_container_width=True)
    else:
        st.info("Данные не загружены. Используйте вкладки загрузки.")

with tab_info:
    st.subheader("Критерии")
    st.markdown("""
| Критерий | Тип | Описание |
|----------|-----|----------|
| **Событие 1 раз в квартал** | 🔴 Критичный | Есть завершенное/перенесенное событие в любом из 3 месяцев |
| **Событие за 2 мес до окончания** | 🔴 Критичный | Есть событие (только для договоров за 30-90 дней до конца) |
| **Счет на продление за 2 мес** | 🔴 Критичный | Выставлен счет (только для договоров за 30-90 дней до конца) |
| **Отсутствие жалоб за 3 мес** | 🟡 Вспомогательный | Клиента нет в списке жалоб |
| **Отсутствие нарядов (отклонен)** | 🟡 Вспомогательный | Нет нарядов со статусом "Отклонен клиентом" |
| **Отсутствие неподписанных док-тов** | 🟡 Вспомогательный | Все документы подписаны или сданы в расчетный отдел |
    """)
    st.subheader("Правила")
    st.markdown("""
- 🟢 **Зеленый**: 0 критичных, < 2 вспомогательных
- 🟡 **Желтый**: 1+ критичных ИЛИ 2+ вспомогательных
- 🔴 **Красный**: 1+ критичных + 2+ вспомогательных ИЛИ 3+ вспомогательных
    """)
