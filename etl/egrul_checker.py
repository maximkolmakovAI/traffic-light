import os
import json
import time
import warnings
import requests
from datetime import datetime
from pathlib import Path
from config import BASE_DIR, LIQUIDATION_CACHE_DAYS

warnings.filterwarnings("ignore", category=DeprecationWarning)
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

CACHE_FILE = BASE_DIR / "data" / "liquidation_cache.json"


def _get_token():
    try:
        import streamlit as st
        return st.secrets.get("DADATA_TOKEN") or os.environ.get("DADATA_TOKEN") or ""
    except Exception:
        return os.environ.get("DADATA_TOKEN", "")


def _load_cache():
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_cache(cache):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _is_fresh(entry):
    checked = entry.get("checked_date", "")
    if not checked:
        return False
    try:
        dt = datetime.fromisoformat(checked)
        return (datetime.now() - dt).days < LIQUIDATION_CACHE_DAYS
    except Exception:
        return False


def check_by_inn(inn):
    if not inn or inn in ("", "nan", "None"):
        return {"status": "unknown", "liquidation_date": None, "source": "no_inn"}

    cache = _load_cache()
    cached = cache.get(inn)
    if cached and _is_fresh(cached):
        return cached

    token = _get_token()
    if not token:
        fallback = cache.get(inn, {})
        if fallback:
            return fallback
        return {"status": "unknown", "liquidation_date": None, "source": "no_token"}

    try:
        url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {token}",
        }
        resp = requests.post(url, json={"query": inn.strip()}, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            suggestions = data.get("suggestions", [])
            if suggestions:
                state = suggestions[0].get("data", {}).get("state", {})
                status = state.get("status", "ACTIVE")
                liq_date = state.get("liquidation_date")

                result = {
                    "status": status,
                    "liquidation_date": liq_date,
                    "source": "dadata",
                    "checked_date": datetime.now().isoformat(),
                    "inn": inn,
                    "name": suggestions[0].get("value", ""),
                }
                cache[inn] = result
                _save_cache(cache)
                return result

        cache[inn] = {
            "status": "unknown",
            "liquidation_date": None,
            "source": "dadata_error",
            "checked_date": datetime.now().isoformat(),
            "inn": inn,
        }
        _save_cache(cache)

    except requests.exceptions.Timeout:
        pass
    except requests.exceptions.ConnectionError:
        pass
    except Exception:
        pass

    fallback = cache.get(inn, {})
    if fallback:
        return fallback
    return {"status": "unknown", "liquidation_date": None, "source": "error"}


def batch_check(inn_list):
    results = {}
    cache = _load_cache()
    to_check = []

    for inn in inn_list:
        if not inn or inn in ("", "nan", "None"):
            results[inn] = {"status": "unknown", "liquidation_date": None, "source": "no_inn"}
            continue
        cached = cache.get(inn)
        if cached and _is_fresh(cached):
            results[inn] = cached
        else:
            to_check.append(inn)

    if not to_check:
        return results

    token = _get_token()
    if not token:
        for inn in to_check:
            results[inn] = cache.get(inn, {"status": "unknown", "liquidation_date": None, "source": "no_token"})
        return results

    import requests
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {token}",
    }

    for inn in to_check:
        try:
            resp = requests.post(url, json={"query": inn.strip()}, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                suggestions = data.get("suggestions", [])
                if suggestions:
                    state = suggestions[0].get("data", {}).get("state", {})
                    result = {
                        "status": state.get("status", "ACTIVE"),
                        "liquidation_date": state.get("liquidation_date"),
                        "source": "dadata",
                        "checked_date": datetime.now().isoformat(),
                        "inn": inn,
                        "name": suggestions[0].get("value", ""),
                    }
                    cache[inn] = result
                    results[inn] = result
                else:
                    results[inn] = {
                        "status": "unknown", "liquidation_date": None,
                        "source": "dadata_not_found", "checked_date": datetime.now().isoformat(), "inn": inn,
                    }
                    cache[inn] = results[inn]
            else:
                results[inn] = cache.get(inn, {
                    "status": "unknown", "liquidation_date": None,
                    "source": "dadata_http_error", "checked_date": datetime.now().isoformat(), "inn": inn,
                })
        except Exception:
            results[inn] = cache.get(inn, {
                "status": "unknown", "liquidation_date": None,
                "source": "error", "checked_date": datetime.now().isoformat(), "inn": inn,
            })

        time.sleep(0.3)

    _save_cache(cache)
    return results
