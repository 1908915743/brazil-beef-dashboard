#!/usr/bin/env python3
"""One-request, read-only test for the Boi capão quote on Notícias Agrícolas.

This is a technical extraction test only. Confirm source-data permissions before
automated collection, storage, or republication. No retries or file writes.
"""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import re
from datetime import datetime

URL = "https://www.noticiasagricolas.com.br/cotacoes/boi-gordo/carcaca-atacado-sp"
USER_AGENT = "Mozilla/5.0 (compatible; PriceMonitorReadOnlyTest/1.0)"


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.cells = []
        self.rows = []
        self.cell_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells = []
        elif tag == "td":
            self.in_td = True
            self.cell_text = []

    def handle_endtag(self, tag):
        if tag == "td" and self.in_td:
            self.cells.append("".join(self.cell_text).strip())
            self.in_td = False
        elif tag == "tr":
            if self.cells:
                self.rows.append(self.cells)

    def handle_data(self, data):
        if self.in_td:
            self.cell_text.append(data)


def parse_date(text):
    patterns = [
        r"\b(\d{2}/\d{2}/\d{4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(raw, fmt).date().isoformat()
                except ValueError:
                    pass
    return None


def main():
    print("Read-only test: Notícias Agrícolas / Boi capão")
    request = Request(URL, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=20) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"RESULT: FAILED - page request error: {exc}")
        raise SystemExit(1)

    parser = TableParser()
    parser.feed(html)

    quote = None
    for row in parser.rows:
        if any("boi capão" in cell.lower() for cell in row):
            quote = row
            break

    if not quote:
        print("RESULT: FAILED - row containing 'Boi capão' not found in HTML table.")
        print("The page may have changed or the quote may not be in server-rendered HTML.")
        raise SystemExit(1)

    label_index = next(i for i, cell in enumerate(quote) if "boi capão" in cell.lower())
    price = None
    for cell in quote[label_index + 1:]:
        match = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2})", cell)
        if match:
            raw = match.group(1)
            price = float(raw.replace(".", "").replace(",", ".")) if "," in raw else float(raw)
            break

    if price is None:
        print(f"RESULT: FAILED - indicator found, but price could not be parsed. Row: {quote}")
        raise SystemExit(1)

    quote_date = parse_date(html)
    print("RESULT: SUCCESS - indicator and price found")
    print("Indicator: Boi capão")
    print(f"Price: {price:.2f}")
    print("Unit: R$/kg")
    print(f"Quote date: {quote_date or 'NOT FOUND'}")
    print("Source page: Notícias Agrícolas")
    print("Mode: one read-only page request; no JSON or dashboard files changed.")
    if quote_date is None:
        print("NOTE: quote date was not detected in the page source; verify it manually.")
    

if __name__ == "__main__":
    main()
