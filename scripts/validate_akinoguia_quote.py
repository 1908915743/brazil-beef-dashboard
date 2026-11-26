#!/usr/bin/env python3
"""Read-only integration validation for AkinoGuia Atacado quote."""
import re
import sys
import urllib.request
from html.parser import HTMLParser

URL = "https://akinoguia.com.br/cotacoes/agropecuarias/atacado"

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell, self.active = [], [], "", False
    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell, self.active = "", True
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.active:
            self.row.append(self.cell.strip())
            self.active = False
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
    def handle_data(self, data):
        if self.active:
            self.cell += data

def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            html = response.read().decode("utf-8", errors="replace")
            print("HTTP:", response.status)
    except Exception as exc:
        print("RESULT: FAILED")
        print("ERROR:", repr(exc))
        sys.exit(1)

    parser = TableParser()
    parser.feed(html)
    date = None
    for row in parser.rows:
        joined = " ".join(row)
        m = re.search(r"(\d{2}/\d{2}/\d{4})", joined)
        if m and ("Atacado" in joined or "SP" in joined):
            date = m.group(1)
            break

    target = next((r for r in parser.rows if any("boi casado capão" in c.lower() for c in r)), None)
    if not target:
        print("RESULT: NOT FOUND")
        print("Rows parsed:", len(parser.rows))
        sys.exit(1)

    if len(target) < 2:
        print("RESULT: PARSE ERROR")
        print("Matched row:", target)
        sys.exit(1)

    price_text = target[1].replace(".", "").replace(",", ".")
    try:
        price = float(price_text)
    except ValueError:
        print("RESULT: PARSE ERROR")
        print("Matched row:", target)
        sys.exit(1)

    print("Indicator: Boi casado capão")
    print("Price:", f"{price:.2f}")
    print("Unit: R$/kg")
    print("Quote date:", date or "NOT FOUND")
    print("Status:", target[2] if len(target) > 2 else "NOT FOUND")
    print("Matched row:", " | ".join(target))
    if not date:
        print("RESULT: DATE NOT FOUND")
        sys.exit(1)
    print("RESULT: SUCCESS")
    print("Read-only validation; no JSON written or published.")

if __name__ == "__main__":
    main()
