from pathlib import Path
p=Path('index.html')
s=p.read_text()
old="direction:debit?'debit':'credit',reconciliation_status:'confirmed'"
new="reconciliation_status:'manual'"
if old not in s: raise SystemExit('financial transaction sequence not found')
s=s.replace(old,new,1)
p.write_text(s)
print('fixed platform_transactions generated direction/check constraint')
