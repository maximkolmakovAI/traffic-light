import streamlit as st
import pandas as pd
import plotly.express as px
import io
from pathlib import Path
from datetime import datetime

from db.database import init_db, get_conn
from etl.loader import run_all_etl
from etl.single_load import load_file_by_buffer, load_file_by_path, check_conflicts, resolve_conflicts
from engine.traffic_light import calculate_traffic_light, get_results_summary, get_details_for_client
from ai_assistant import ask_ai

st.set_page_config(page_title="Светофор по клиентам", page_icon="🚦", layout="wide")

COLOR_LABEL = {"green": "Зеленый", "yellow": "Желтый", "red": "Красный"}
COLOR_HEX = {"green": "#2ecc71", "yellow": "#f1c40f", "red": "#e74c3c"}
COLOR_SUBTLE = {"green": "#d4edda", "yellow": "#fff3cd", "red": "#f8d7da"}

st.markdown("""
<style>
    .color-green { background-color: #d4edda; }
    .color-yellow { background-color: #fff3cd; }
    .color-red { background-color: #f8d7da; }
    .chat-msg { padding: 0.5rem; margin: 0.25rem 0; border-radius: 0.5rem; }
    .chat-user { background-color: #e3f2fd; }
    .chat-ai { background-color: #f5f5f5; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        gap: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)


def load_traffic_data():
    conn = get_conn()
    df = pd.read_sql("""
        SELECT t.client_name AS "Клиент",
               t.manager AS "Менеджер",
               t.contract_end AS "Дата окончания договора",
               CASE t.crit_event_quarter WHEN 1 THEN '✅' ELSE '❌' END AS "Событие 1р/кв",
               CASE t.crit_no_complaints WHEN 1 THEN '✅' ELSE '❌' END AS "Нет жалоб",
               CASE t.crit_no_rejected_orders WHEN 1 THEN '✅' ELSE '❌' END AS "Нет нарядов",
               CASE t.crit_event_before_end WHEN 1 THEN '✅' ELSE '❌' END AS "Событие за 2 мес",
               CASE t.crit_invoice_before_end WHEN 1 THEN '✅' ELSE '❌' END AS "Счет на продление",
               CASE t.crit_no_unsigned_docs WHEN 1 THEN '✅' ELSE '❌' END AS "Неподписанные док-ты",
               t.critical_bad AS "Крит.наруш",
               t.auxiliary_bad AS "Вспом.наруш",
               t.final_color AS "Цвет"
        FROM traffic_light_results t
        ORDER BY CASE t.final_color WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END, t.client_name
    """, conn)
    conn.close()
    return df


def render_color_row(row):
    color = row.get("Цвет", "green")
    bg = COLOR_SUBTLE.get(color, "#ffffff")
    return [f"background-color: {bg}"] * len(row)


init_db()

st.title("🚦 Светофор по клиентской базе")

left_col, right_col = st.columns([3, 2])

with right_col:
    st.subheader("💬 ИИ-ассистент")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    chat_container = st.container(height=450)
    with chat_container:
        if not st.session_state.chat_history:
            st.caption("Спросите о данных: например, «сколько красных клиентов?» или «расскажи про клиента ЛТК»")

        for msg in st.session_state.chat_history:
            role_class = "chat-user" if msg["role"] == "user" else "chat-ai"
            st.markdown(
                f"""<div class="{role_class}" style="padding:0.5rem;margin:0.25rem 0;border-radius:0.5rem">
                <small>{msg["content"][:300]}</small></div>""",
                unsafe_allow_html=True
            )

    user_input = st.chat_input("Задайте вопрос о данных...", key="ai_chat_input")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input, "timestamp": datetime.now().isoformat()})

        with st.spinner("ИИ анализирует..."):
            reply = ask_ai(user_input, st.session_state.chat_history)

        st.session_state.chat_history.append({"role": "assistant", "content": reply, "timestamp": datetime.now().isoformat()})
        st.rerun()

    if st.session_state.chat_history and st.button("🗑️ Очистить диалог", use_container_width=True, key="clear_chat"):
        st.session_state.chat_history = []
        st.rerun()

with left_col:
    tab_main, tab_upload_single, tab_upload_folder, tab_info = st.tabs([
        "📊 Светофор", "📂 Загрузить файл", "📁 Загрузить папку", "ℹ️ Описание"
    ])

    with tab_upload_single:
        st.info("⚠️ **Недоступно в тестовой версии.** Будет добавлено в следующих релизах.")
        uploaded_file = st.file_uploader("Выберите Excel-файл отчета", type=["xls", "xlsx"], key="single_upload")

        if uploaded_file is not None:
            file_bytes = uploaded_file.read()
            buf = io.BytesIO(file_bytes)

            from etl.file_detector import detect_file_type
            detection = detect_file_type(uploaded_file.name, buf)

            if detection["file_type"] == "unknown":
                st.error(f"Не удалось определить тип файла: {uploaded_file.name}")
            else:
                st.info(f"**Определен тип:** {detection['label']}")

                batch_id = int(datetime.now().timestamp())
                state_key = f"conflict_{uploaded_file.name}"

                if st.session_state.get(state_key) != "resolved":
                    conflicts = check_conflicts(detection["file_type"], detection["period"])
                    if conflicts:
                        st.warning("Обнаружены конфликты: данные уже существуют в базе")
                        for c in conflicts:
                            st.write(f"- {c['message']}")

                        col_a, col_b, col_c = st.columns(3)
                        if col_a.button("🔄 Перезаписать", key=f"rep_{uploaded_file.name}", use_container_width=True):
                            buf.seek(0)
                            result = load_file_by_buffer(buf, uploaded_file.name, batch_id, resolution="replace")
                            if result["success"]:
                                resolve_conflicts(detection["file_type"], detection["period"], "replace", batch_id)
                                st.success(f"Загружено {result['loaded']} записей!")
                                st.session_state[state_key] = "resolved"
                                st.rerun()
                            else:
                                st.error(f"Ошибка: {result.get('error','')}")

                        if col_b.button("⏭️ Пропустить", key=f"skip_{uploaded_file.name}", use_container_width=True):
                            st.info("Загрузка пропущена")
                            st.session_state[state_key] = "resolved"
                            st.rerun()

                        if col_c.button("❌ Отменить", key=f"can_{uploaded_file.name}", use_container_width=True):
                            st.session_state[state_key] = "cancelled"
                            st.rerun()
                    else:
                        buf.seek(0)
                        with st.spinner("Загрузка..."):
                            result = load_file_by_buffer(buf, uploaded_file.name, batch_id)
                        if result["success"]:
                            st.success(f"✅ Загружено {result['loaded']} записей!")
                            st.session_state[state_key] = "resolved"
                        else:
                            st.error(f"Ошибка: {result.get('error','')}")

    with tab_upload_folder:
        st.info("⚠️ **Недоступно в тестовой версии.** Будет добавлено в следующих релизах.")
        folder_path = st.text_input(
            "Путь к папке с отчетами",
            value=str(Path(r"C:\AI_ALL\Разработка 1С на OpenCode\Анализ отчетов для Вали\Исходные отчеты")),
            key="folder_path_input",
        )

        if st.button("📂 Загрузить все файлы из папки", use_container_width=True):
            folder = Path(folder_path)
            if not folder.exists():
                st.error(f"Папка не найдена: {folder_path}")
            else:
                batch_id = int(datetime.now().timestamp())
                results = []
                errors = []

                progress = st.progress(0, text="Загрузка файлов...")
                files = []
                for ext in ["*.xls", "*.xlsx"]:
                    files.extend(sorted(folder.glob(ext)))
                for ext in ["*.XLS", "*.XLSX"]:
                    files.extend(sorted(folder.glob(ext)))

                for i, filepath in enumerate(files):
                    progress.progress((i + 1) / len(files), text=f"Обработка: {filepath.name}")
                    result = load_file_by_path(filepath, batch_id, resolution="replace")
                    results.append(result)
                    if not result["success"]:
                        errors.append(f"{filepath.name}: {result.get('error','')}")

                progress.empty()
                total = sum(r.get("loaded", 0) for r in results if r.get("success"))
                success_cnt = sum(1 for r in results if r.get("success"))
                st.success(f"✅ Загружено {success_cnt}/{len(files)} файлов, всего {total} записей")

                if errors:
                    with st.expander("Ошибки"):
                        for e in errors:
                            st.write(f"- {e}")

                if success_cnt > 0 and st.button("📊 Рассчитать светофор", use_container_width=True):
                    with st.spinner("Расчет..."):
                        calculate_traffic_light()
                    st.success("Светофор пересчитан!")
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
            with st.spinner("Загрузка..."):
                run_all_etl(clear_first=True)
            with st.spinner("Расчет светофора..."):
                calculate_traffic_light()
            st.success("Готово!")
            st.rerun()

        if col2.button("📊 Пересчитать светофор", use_container_width=True):
            with st.spinner("Расчет..."):
                calculate_traffic_light()
            st.success("Готово!")
            st.rerun()

        if total > 0:
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("🟢 Зеленая зона", counts.get("green", 0),
                       f"{counts.get('green',0)/total*100:.0f}%" if total else "0%", border=True)
            mc2.metric("🟡 Желтая зона", counts.get("yellow", 0),
                       f"{counts.get('yellow',0)/total*100:.0f}%" if total else "0%", border=True)
            mc3.metric("🔴 Красная зона", counts.get("red", 0),
                       f"{counts.get('red',0)/total*100:.0f}%" if total else "0%", border=True)

            st.divider()

            df = load_traffic_data()
            if not df.empty:
                filt1, filt2 = st.columns(2)
                with filt1:
                    managers = ["Все"] + sorted(df["Менеджер"].unique().tolist())
                    selected_manager = st.selectbox("Менеджер", managers, key="mgr_filter")
                with filt2:
                    color_opts = ["Все", "green", "yellow", "red"]
                    selected_color = st.selectbox(
                        "Зона", color_opts,
                        format_func=lambda x: COLOR_LABEL.get(x, "Все") if x != "Все" else "Все",
                        key="col_filter",
                    )

                fdf = df.copy()
                if selected_manager != "Все":
                    fdf = fdf[fdf["Менеджер"] == selected_manager]
                if selected_color != "Все":
                    fdf = fdf[fdf["Цвет"] == selected_color]

                display_cols = [c for c in fdf.columns if c != "Цвет"]

                styled = fdf.style.apply(render_color_row, axis=1)
                st.dataframe(
                    styled,
                    use_container_width=True,
                    height=500,
                    column_config={"Клиент": st.column_config.TextColumn(width="medium")},
                )

                selected_client = st.selectbox("🔍 Показать детали по клиенту", [""] + sorted(fdf["Клиент"].unique().tolist()))
                if selected_client:
                    st.caption(f"Детализация для: {selected_client}")
                    details = get_details_for_client(selected_client)
                    if details:
                        for d in details:
                            icon = "✅" if d["status"] else "❌"
                            st.markdown(f"**{icon} {d['criterion_name']}**  \n{d['reasoning']}")
                    else:
                        st.caption("Нет детальных данных (возможно, светофор не пересчитан)")

                csv = fdf.to_csv(index=False).encode("utf-8-sig")
                st.download_button("⬇️ Скачать CSV", csv, "svetofor.csv", "text/csv", use_container_width=True)

                st.divider()
                pie_fig = px.pie(
                    names=["Зеленый", "Желтый", "Красный"],
                    values=[counts.get("green", 0), counts.get("yellow", 0), counts.get("red", 0)],
                    color=["Зеленый", "Желтый", "Красный"],
                    color_discrete_map={"Зеленый": "#2ecc71", "Желтый": "#f1c40f", "Красный": "#e74c3c"},
                    title="Распределение клиентов",
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
