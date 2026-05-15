import json
import os
import requests
from datetime import datetime
from db.database import get_conn

API_URL = "https://litellm.1bitai.ru/chat/completions"

try:
    import streamlit as st
    API_KEY = st.secrets.get("AI_API_KEY", os.environ.get("AI_API_KEY", "sk-2dbPPD0-PWa-1GUgVfonjg"))
except Exception:
    API_KEY = os.environ.get("AI_API_KEY", "sk-2dbPPD0-PWa-1GUgVfonjg")

MODELS = ["ollama/qwen3.5:35b", "qwen3.5:35b", "ollama/llama3.2:3b", "llama3.2:3b"]
MAX_SUMMARY_LINES = 100
SESSION_TIMEOUT_MINUTES = 60


def _build_system_prompt():
    return """Ты — ассистент-аналитик по системе "Светофор клиентской базы". 
Твоя задача — помогать пользователю анализировать данные светофора.

Система оценивает клиентов по 6 критериям:
1. 🔴 Событие 1 раз в квартал (критичный) — должно быть завершенное/перенесенное событие хотя бы в 1 из 3 месяцев
2. 🟡 Отсутствие жалоб за 3 мес (вспомогательный) — клиента не должно быть в списке жалоб
3. 🟡 Отсутствие нарядов "отклонен клиентом" (вспомогательный) — нет нарядов с таким статусом
4. 🔴 Событие за 2 мес до окончания (критичный) — есть событие (только для договоров, заканчивающихся через 30-90 дней)
5. 🔴 Счет на продление за 2 мес до окончания (критичный) — есть счет (только для договоров, заканчивающихся через 30-90 дней)
6. 🟡 Отсутствие неподписанных документов (вспомогательный) — все документы подписаны электронно или сданы в расчетный отдел

Правила светофора:
- Зеленый: 0 критичных нарушений и < 2 вспомогательных
- Желтый: 1+ критичных ИЛИ 2+ вспомогательных
- Красный: 1+ критичных + 2+ вспомогательных ИЛИ 3+ вспомогательных

Отвечай кратко, по делу, на русском языке. Если пользователь спрашивает про конкретного клиента — покажи детальную расшифровку по каждому критерию."""


def _get_traffic_light_context(limit_rows=20):
    conn = get_conn()
    cur = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN final_color='red' THEN 1 ELSE 0 END) as red,
               SUM(CASE WHEN final_color='yellow' THEN 1 ELSE 0 END) as yellow,
               SUM(CASE WHEN final_color='green' THEN 1 ELSE 0 END) as green
        FROM traffic_light_results
    """)
    stats = dict(cur.fetchone())
    context = f"Всего клиентов: {stats['total']}, Красных: {stats['red']}, Желтых: {stats['yellow']}, Зеленых: {stats['green']}.\n\n"

    cur = conn.execute("""
        SELECT client_name, final_color, critical_bad, auxiliary_bad
        FROM traffic_light_results
        ORDER BY CASE final_color WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END
        LIMIT ?
    """, (limit_rows,))
    clients = cur.fetchall()
    if clients:
        context += "Клиенты:\n"
        for r in clients:
            context += f"- {r['client_name']}: {r['final_color']} (крит.нарушений: {r['critical_bad']}, вспом.нарушений: {r['auxiliary_bad']})\n"
    conn.close()
    return context


def _get_client_detail(client_name):
    conn = get_conn()
    cur = conn.execute("""
        SELECT client_name, final_color, critical_bad, auxiliary_bad,
               crit_event_quarter, crit_no_complaints, crit_no_rejected_orders,
               crit_event_before_end, crit_invoice_before_end, crit_no_unsigned_docs
        FROM traffic_light_results WHERE client_name = ?
    """, (client_name,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return f"Клиент '{client_name}' не найден в результатах светофора."

    text = f"Клиент: {row['client_name']}\n"
    text += f"Итоговый цвет: {row['final_color']}\n"
    text += f"Критических нарушений: {row['critical_bad']}, Вспомогательных нарушений: {row['auxiliary_bad']}\n\n"

    cur2 = conn.execute("""
        SELECT criterion_name, status, reasoning
        FROM traffic_light_details WHERE client_name = ?
    """, (client_name,))
    for d in cur2.fetchall():
        status_str = "✅" if d['status'] else "❌"
        text += f"{status_str} {d['criterion_name']}: {d['reasoning']}\n"

    conn.close()
    return text


def _summarize_history(messages):
    summary_parts = []
    for m in messages:
        role = "Пользователь" if m["role"] == "user" else "Ассистент"
        content = m["content"][:200]
        summary_parts.append(f"{role}: {content}")
    combined = "\n".join(summary_parts)
    lines = combined.split("\n")
    if len(lines) > MAX_SUMMARY_LINES:
        lines = lines[-MAX_SUMMARY_LINES:]
    return "\n".join(lines)


def ask_ai(user_message, chat_history):
    now = datetime.now()
    context = _get_traffic_light_context(20)

    system_prompt = _build_system_prompt()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"Текущие данные светофора:\n{context}"},
    ]

    history = chat_history[-8:] if chat_history else []

    for h in history:
        msg_time = h.get("timestamp", "")
        if msg_time:
            try:
                t = datetime.fromisoformat(msg_time)
                if (now - t).total_seconds() > SESSION_TIMEOUT_MINUTES * 60:
                    messages = messages[:2]
                    break
            except ValueError:
                pass
        messages.append({"role": h["role"], "content": h["content"]})

    client_match = None
    for prefix in ["по клиенту", "клиент", "расскажи про", "что с"]:
        if prefix in user_message.lower():
            parts = user_message.split(prefix, 1)
            if len(parts) > 1:
                candidate = parts[1].strip().strip('"').strip("'").strip("«").strip("»")
                if candidate:
                    client_match = candidate
                    break

    if client_match:
        detail = _get_client_detail(client_match)
        messages.append({"role": "system", "content": f"Детали по клиенту {client_match}:\n{detail}"})

    messages.append({"role": "user", "content": user_message})

    last_err = ""
    for model in MODELS:
        try:
            resp = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
                timeout=120,
                verify=False,
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            return reply
        except requests.exceptions.Timeout:
            last_err = "⏳ Сервер ИИ не ответил вовремя."
        except requests.exceptions.HTTPError as e:
            last_err = f"⚠️ Сервер ИИ временно недоступен (модель {model}). Попробуйте позже."
            if e.response.status_code != 500:
                last_err = f"⚠️ Ошибка HTTP {e.response.status_code}: {e.response.text[:200]}"
        except Exception as e:
            last_err = f"⚠️ Ошибка подключения к ИИ: {e}"
    return last_err
