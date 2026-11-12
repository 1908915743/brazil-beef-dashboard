#!/usr/bin/env python3
"""Update dashboard prices from the configured source feeds."""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "wholesale_price.json"

# This endpoint was observed in the PFSC site's own report-list request.
# Confirm permission/terms for automated business use before enabling scheduled calls.
MOA_REPORT_API = os.getenv("MOA_WHOLESALE_API_URL", "").strip() or "https://pfsc.agri.cn/api/FarmDaily/list"
MOA_PAGE_SIZE = 10


def extract_beef_price(report):
    """Return (price, quote_date) from one FarmDaily report, or None."""
    if not isinstance(report, dict):
        return None
    summary = report.get("animalConclusion") or ""
    if not isinstance(summary, str):
        return None

    # Handles both '牛肉74.10元/公斤' and '牛肉平均价格为74.10元/公斤'.
    match = re.search(r"牛肉(?:平均价格为|平均价格|价格为)?\s*([0-9]+(?:\.[0-9]+)?)\s*元/公斤", summary)
    if not match:
        return None

    raw_date = report.get("daylyDate") or report.get("dailyDate") or ""
    if not isinstance(raw_date, str) or len(raw_date) < 10:
        return None
    quote_date = raw_date[:10]
    try:
        datetime.strptime(quote_date, "%Y-%m-%d")
        value = float(match.group(1))
    except ValueError:
        return None
    return value, quote_date


def fetch_moa_beef():
    body = json.dumps({"pageNum": 1, "pageSize": MOA_PAGE_SIZE}).encode("utf-8")
    request = Request(
        MOA_REPORT_API,
        data=body,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (compatible; beef-price-dashboard/1.0)",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, dict) or payload.get("code") != 200:
        raise ValueError("PFSC report API returned an unexpected response")
    content = payload.get("content") or {}
    reports = content.get("list") if isinstance(content, dict) else None
    if not isinstance(reports, list):
        raise ValueError("PFSC response does not contain content.list")

    quotes = [quote for row in reports if (quote := extract_beef_price(row))]
    if not quotes:
        raise ValueError("No dated beef price found in the latest report page")
    return max(quotes, key=lambda quote: quote[1])


def main():
    try:
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except Exception:
        old = {"items": []}
    previous = {
        item.get("id"): item
        for item in old.get("items", [])
        if isinstance(item, dict)
    }

    china = dict(previous.get("china_beef_wholesale", {}))
    china.update({
        "id": "china_beef_wholesale",
        "name": "全国牛肉平均批发价格",
        "unit": "元/公斤",
        "source_name": "农业农村部农产品批发市场每日报告",
        "source_url": "https://pfsc.agri.cn/#/analysisReport",
    })
    failures = []
    try:
        value, quote_date = fetch_moa_beef()
        china.update({
            "value": value,
            "quote_date": quote_date,
            "status": "已更新",
        })
        print(f"china_beef_wholesale: {value} 元/公斤 ({quote_date})")
    except Exception as exc:
        china["status"] = "更新失败，保留上次有效数据"
        failures.append("china_beef_wholesale")
        print(f"china_beef_wholesale failed: {type(exc).__name__}: {exc}")
    items = [china]

    # Scot remains independently disabled until an authorized feed is supplied.
    scot = dict(previous.get("brazil_carcaca_casada", {}))
    scot.update({
        "id": "brazil_carcaca_casada",
        "name": "Carcaça Casada（牛胴体批发价）",
        "unit": "R$/kg",
        "source_name": "Scot Consultoria",
        "source_url": "https://www.scotconsultoria.com.br/cotacoes/",
    })
    if not os.getenv("SCOT_CARCACA_API_URL", "").strip():
        scot.setdefault("value", None)
        scot.setdefault("quote_date", None)
        scot["status"] = "待取得Scot授权及数据接口"
    else:
        # The Scot adapter needs its provider's actual authorized response schema.
        scot["status"] = "已配置接口，待适配并验证数据格式"
    items.append(scot)

    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "update_status": "partial" if failures else "ok",
        "items": items,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
