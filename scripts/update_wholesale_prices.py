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

    # The official daily brief usually states the day-on-day direction and percentage.
    change_match = re.search(
        r"牛肉[^；;。]{0,120}?比昨天(上升|下降)([0-9]+(?:\.[0-9]+)?)%",
        summary,
    )
    raw_date = report.get("daylyDate") or report.get("dailyDate") or ""
    if not isinstance(raw_date, str) or len(raw_date) < 10:
        return None
    quote_date = raw_date[:10]
    try:
        datetime.strptime(quote_date, "%Y-%m-%d")
        value = float(match.group(1))
        change_pct = float(change_match.group(2)) if change_match else None
    except ValueError:
        return None
    return {
        "value": value,
        "quote_date": quote_date,
        "change_pct": change_pct,
        "change_direction": (
            "up" if change_match and change_match.group(1) == "上升"
            else "down" if change_match else None
        ),
        "daily_brief": summary,
        "report_title": report.get("conclusion") or "",
    }


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

    # Sort distinct report dates so the absolute day-on-day change is based
    # on the immediately preceding published report, not an assumed calendar day.
    by_date = {}
    for quote in quotes:
        by_date[quote["quote_date"]] = quote
    ordered = sorted(by_date.values(), key=lambda quote: quote["quote_date"], reverse=True)
    latest = dict(ordered[0])
    if len(ordered) > 1:
        previous = ordered[1]
        latest["change_value"] = round(latest["value"] - previous["value"], 2)
        latest["previous_value"] = previous["value"]
        latest["previous_quote_date"] = previous["quote_date"]
    else:
        latest["change_value"] = None
        latest["previous_value"] = None
        latest["previous_quote_date"] = None
    return latest


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
        quote = fetch_moa_beef()
        china.update({
            "value": quote["value"],
            "quote_date": quote["quote_date"],
            "change_value": quote.get("change_value"),
            "previous_value": quote.get("previous_value"),
            "previous_quote_date": quote.get("previous_quote_date"),
            "change_pct": quote["change_pct"],
            "change_direction": quote["change_direction"],
            "daily_brief": quote["daily_brief"],
            "report_title": quote["report_title"],
            "status": "已更新",
        })
        print(
            f"china_beef_wholesale: {quote['value']} 元/公斤 "
            f"({quote['quote_date']}); day-on-day: "
            f"{quote['change_direction'] or '未提供'} "
            f"{quote['change_pct'] if quote['change_pct'] is not None else 'N/A'}%; "
            f"absolute change: {quote.get('change_value') if quote.get('change_value') is not None else 'N/A'} 元/公斤; "
            f"previous quote: {quote.get('previous_quote_date') or 'N/A'}"
        )
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
