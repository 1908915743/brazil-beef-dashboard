#!/usr/bin/env python3
"""Update dashboard prices from the configured source feeds."""
import json
import os
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "wholesale_price.json"

# This endpoint was observed in the PFSC site's own report-list request.
# Confirm permission/terms for automated business use before enabling scheduled calls.
MOA_REPORT_API = os.getenv("MOA_WHOLESALE_API_URL", "").strip() or "https://pfsc.agri.cn/api/FarmDaily/list"
MOA_PAGE_SIZE = 10




class AkinoGuiaParser(HTMLParser):
    """Parse the visible Atacado table without executing page scripts."""
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell, self.in_cell = [], [], "", False
    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell, self.in_cell = "", True
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            self.row.append(self.cell.strip())
            self.in_cell = False
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
    def handle_data(self, data):
        if self.in_cell:
            self.cell += data


def fetch_akinoguia_quote():
    url = "https://akinoguia.com.br/cotacoes/agropecuarias/atacado"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; beef-price-dashboard/1.0)"})
    with urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError(f"AkinoGuia returned HTTP {response.status}")
        html = response.read().decode("utf-8", errors="replace")
    parser = AkinoGuiaParser()
    parser.feed(html)
    quote_date = None
    for row in parser.rows:
        joined = " ".join(row)
        match = re.search(r"(\d{2}/\d{2}/\d{4})", joined)
        if match and ("Atacado" in joined or "SP" in joined):
            quote_date = datetime.strptime(match.group(1), "%d/%m/%Y").date().isoformat()
            break
    target = next((row for row in parser.rows if any("boi casado capão" in cell.lower() for cell in row)), None)
    if not target or len(target) < 2:
        raise ValueError("AkinoGuia target quote row was not found")
    price_text = target[1].replace(".", "").replace(",", ".")
    value = float(price_text)
    if not quote_date:
        raise ValueError("AkinoGuia quote date was not found")
    status = target[2] if len(target) > 2 else ""
    return {"value": value, "quote_date": quote_date, "status": status}



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

    # AkinoGuia public page: read only the specific quote row and page date.
    brazil = dict(previous.get("brazil_carcaca_casada", {}))
    brazil.update({
        "id": "brazil_carcaca_casada",
        "name": "Boi casado capão（阉牛整胴体批发价）",
        "unit": "R$/kg",
        "source_name": "AkinoGuia（页面标注来源 Scot Consultoria）",
        "source_url": "https://akinoguia.com.br/cotacoes/agropecuarias/atacado",
    })
    try:
        quote = fetch_akinoguia_quote()
        previous_brazil_value = brazil.get("value")
        previous_brazil_date = brazil.get("quote_date")
        brazil.update({
            "value": quote["value"],
            "quote_date": quote["quote_date"],
            "change_value": None,
            "change_pct": None,
            "change_direction": "flat" if quote["status"].lower() in ("estável", "stable") else None,
            "status": "已更新" if quote["status"].lower() in ("estável", "stable") else "已更新（涨跌未核实）",
            "page_status": quote["status"],
            "previous_value": previous_brazil_value,
            "previous_quote_date": previous_brazil_date,
        })
        print(f'brazil_carcaca_casada: {quote["value"]} R$/kg ({quote["quote_date"]}); page status: {quote["status"]}')
    except Exception as exc:
        brazil["status"] = "更新失败，保留上次有效数据"
        failures.append("brazil_carcaca_casada")
        print(f"brazil_carcaca_casada failed: {type(exc).__name__}: {exc}")
    items.append(brazil)

    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "update_status": "partial" if failures else "ok",
        "items": items,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
