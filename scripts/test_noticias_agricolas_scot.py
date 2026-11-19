#!/usr/bin/env python3
"""One-off, read-only test for the Boi capao quote shown on Noticias Agricolas.

This script fetches one public page and prints the matching quote. It does not
write wholesale_price.json or change the dashboard. Obtain permission from the
publisher/data owner before using the data in scheduled or commercial workflows.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PAGE_URL = "https://www.noticiasagricolas.com.br/cotacoes/boi-gordo/carcaca-atacado-sp"
TARGET_LABEL = "Boi capao"
TIMEOUT_SECONDS = 25


class QuoteTableParser(HTMLParser):
    """Read table rows inside tbody.body-box and collect visible page text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_target_body = False
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row_cells: list[str] = []
        self.rows: list[list[str]] = []
        self.page_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tbody" and "body-box" in (attrs_dict.get("class") or "").split():
            self.in_target_body = True
        elif tag == "tr" and self.in_target_body:
            self.in_row = True
            self.row_cells = []
        elif tag == "td" and self.in_row:
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        self.page_text_parts.append(data)
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            value = " ".join(" ".join(self.cell_parts).split())
            self.row_cells.append(value)
            self.cell_parts = []
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            self.rows.append(self.row_cells)
            self.row_cells = []
            self.in_row = False
        elif tag == "tbody" and self.in_target_body:
            self.in_target_body = False


def fetch_page() -> str:
    request = Request(
        PAGE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; PriceDashboardReadOnlyTest/1.0)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def parse_quote(html: str) -> tuple[float, str, str]:
    parser = QuoteTableParser()
    parser.feed(html)

    matched_price: str | None = None
    for cells in parser.rows:
        if len(cells) >= 2 and cells[0].strip().casefold() == TARGET_LABEL.casefold():
            matched_price = cells[1].strip()
            break

    if not matched_price:
        raise ValueError(
            f"Could not find '{TARGET_LABEL}' in tbody.body-box. "
            "The page structure may have changed."
        )

    # Brazilian notation uses comma as decimal separator (e.g. 26,10).
    numeric_text = re.sub(r"[^0-9.,]", "", matched_price)
    if "," in numeric_text:
        numeric_text = numeric_text.replace(".", "").replace(",", ".")
    value = float(numeric_text)

    page_text = " ".join(" ".join(parser.page_text_parts).split())
    date_match = re.search(
        r"Fechamento\s*:\s*(\d{2}/\d{2}/\d{4})",
        page_text,
        flags=re.IGNORECASE,
    )
    if not date_match:
        raise ValueError(
            "Found the price but could not find the 'Fechamento' quote date."
        )
    quote_date = datetime.strptime(date_match.group(1), "%d/%m/%Y").date().isoformat()

    unit_match = re.search(r"Pre[cç]os\s+em\s+R\$\s*/\s*KG", page_text, flags=re.IGNORECASE)
    unit = "R$/kg" if unit_match else "R$/kg (expected unit; page heading not detected)"
    return value, quote_date, unit


def main() -> int:
    print("Read-only test: Notícias Agrícolas / Boi capao")
    print(f"Page: {PAGE_URL}")
    try:
        html = fetch_page()
        value, quote_date, unit = parse_quote(html)
    except HTTPError as exc:
        print(f"ERROR: HTTP {exc.code} while fetching the page.")
        return 1
    except URLError as exc:
        print(f"ERROR: Could not reach the page: {exc.reason}")
        return 1
    except (TimeoutError, OSError) as exc:
        print(f"ERROR: Network/read failure: {exc}")
        return 1
    except (ValueError, TypeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print("RESULT: SUCCESS")
    print(f"Indicator: {TARGET_LABEL} (阉牛整胴体)")
    print(f"Price: {value:.2f}")
    print(f"Unit: {unit}")
    print(f"Quote date: {quote_date}")
    print("Mode: one page request; no JSON or dashboard files changed.")
    print("Reminder: confirm publisher/data-owner permission before scheduled or commercial reuse.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
