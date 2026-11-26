#!/usr/bin/env python3
"""One-shot read-only test for AcheiMa+ beef wholesale quote page."""
import re, sys, urllib.request
from html.parser import HTMLParser
URL = "https://acheima.com.br/cotacoes/agropecuarias/atacado"
class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=[]; self.cell=""; self.in_cell=False
    def handle_starttag(self,t,a):
        if t=="tr": self.row=[]
        elif t in ("td","th"): self.cell=""; self.in_cell=True
    def handle_endtag(self,t):
        if t in ("td","th") and self.in_cell: self.row.append(self.cell.strip()); self.in_cell=False
        elif t=="tr" and self.row: self.rows.append(self.row)
    def handle_data(self,d):
        if self.in_cell: self.cell+=d
def main():
    try:
        req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=20) as r:
            html=r.read().decode("utf-8",errors="replace"); print("HTTP:",r.status)
    except Exception as e:
        print("RESULT: FAILED"); print("ERROR:",repr(e)); sys.exit(1)
    p=Parser(); p.feed(html)
    hits=[row for row in p.rows if any("boi casado capao" in c.lower() for c in row)]
    if not hits:
        print("RESULT: NOT FOUND"); print("Rows parsed:",len(p.rows)); sys.exit(1)
    print("Matched row:", " | ".join(hits[0]))
    print("RESULT: SUCCESS (row found; manually verify quote/date)")
    print("Note: one-time read only; no storage or publishing.")
if __name__=="__main__": main()
