#!/usr/bin/env python3
"""One-time, read-only HTML test of AkinoGuia Atacado page."""
import sys, urllib.request
from html.parser import HTMLParser
URL="https://akinoguia.com.br/cotacoes/agropecuarias/atacado"
class P(HTMLParser):
 def __init__(self):
  super().__init__(); self.rows=[]; self.row=[]; self.cell=""; self.active=False
 def handle_starttag(self,t,a):
  if t=="tr": self.row=[]
  elif t in ("td","th"): self.cell=""; self.active=True
 def handle_endtag(self,t):
  if t in ("td","th") and self.active: self.row.append(self.cell.strip()); self.active=False
  elif t=="tr" and self.row: self.rows.append(self.row)
 def handle_data(self,d):
  if self.active:self.cell+=d
def main():
 try:
  req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0"})
  with urllib.request.urlopen(req,timeout=20) as r:
   html=r.read().decode("utf-8",errors="replace");print("HTTP:",r.status)
 except Exception as e:
  print("RESULT: FAILED");print("ERROR:",repr(e));sys.exit(1)
 p=P();p.feed(html)
 hits=[row for row in p.rows if any("boi casado capao" in c.lower() for c in row)]
 if not hits:
  print("RESULT: NOT FOUND");print("Rows parsed:",len(p.rows));sys.exit(1)
 print("Matched row:", " | ".join(hits[0]))
 print("RESULT: SUCCESS (quote row found; verify date/price manually)")
 print("Read-only test; does not store or publish data.")
if __name__=="__main__":main()
