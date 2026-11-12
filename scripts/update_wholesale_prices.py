#!/usr/bin/env python3
"""Fetch authorized, normalized JSON feeds for the dashboard price brief."""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "wholesale_price.json"
SOURCES = [
    ("china_beef_wholesale", "MOA_WHOLESALE_API_URL", "全国牛肉平均批发价格", "元/公斤", "待申请官方数据接口", "农业农村部重点农产品市场信息平台", "https://ncpscxx.moa.gov.cn/"),
    ("brazil_carcaca_casada", "SCOT_CARCACA_API_URL", "Carcaça Casada（牛胴体批发价）", "R$/kg", "待取得Scot授权及数据接口", "Scot Consultoria", "https://www.scotconsultoria.com.br/cotacoes/"),
]

def main():
    try:
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except Exception:
        old = {"items": []}
    previous = {x.get("id"): x for x in old.get("items", []) if isinstance(x, dict)}
    items, failures = [], []
    for item_id, env, name, unit, pending, source_name, source_url in SOURCES:
        item = dict(previous.get(item_id, {}))
        item.update({"id": item_id, "name": name, "unit": unit,
                     "source_name": source_name, "source_url": source_url})
        endpoint = os.getenv(env, "").strip()
        if not endpoint:
            item.setdefault("value", None)
            item.setdefault("quote_date", None)
            item["status"] = pending
            print(f"{item_id}: skipped; {env} is not configured")
            items.append(item)
            continue
        try:
            req = Request(endpoint, headers={"Accept": "application/json", "User-Agent": "brazil-beef-dashboard/1.0"})
            with urlopen(req, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8"))
            fresh = payload.get("item") if isinstance(payload, dict) else None
            if not isinstance(fresh, dict) or fresh.get("id") != item_id:
                raise ValueError("response item.id mismatch or missing item object")
            value = fresh.get("value")
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise ValueError("value must be numeric or null")
            if value is not None and not fresh.get("quote_date"):
                raise ValueError("quote_date is required when value is present")
            for key in ("value", "unit", "quote_date", "change_value", "change_pct"):
                if key in fresh: item[key] = fresh[key]
            item["status"] = "已更新"
            print(f"{item_id}: updated")
        except Exception as exc:
            item["status"] = "更新失败，保留上次有效数据"
            failures.append(item_id)
            print(f"{item_id}: failed: {type(exc).__name__}: {exc}")
        items.append(item)
    result = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "update_status": "partial" if failures else "ok", "items": items}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    sys.exit(main())
