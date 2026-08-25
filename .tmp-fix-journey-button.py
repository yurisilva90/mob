from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')

old = "function renderJourneyCard(day, isToday) {\n  const jc = document.getElementById('journey-card');\n  if (!jc) return;\n"
new = "function renderJourneyCard(day, isToday) {\n  const jc = document.getElementById('journey-card');\n  if (!jc) return;\n  const cardDate = day?.date || S.curDate || DB.today();\n"
if s.count(old) != 1:
    raise SystemExit(f'cabecalho renderJourneyCard inesperado: {s.count(old)}')
s = s.replace(old, new, 1)

replacements = [
    ("const autoTripsReady = S._autoTripsDataDate === d;", "const autoTripsReady = S._autoTripsDataDate === cardDate;", 1),
    ("pcbEl.dataset.dataDate = d;", "pcbEl.dataset.dataDate = cardDate;", 2),
    ("pcbEl.dataset.dataDate !== d", "pcbEl.dataset.dataDate !== cardDate", 1),
]
for old_text, new_text, expected in replacements:
    found = s.count(old_text)
    if found != expected:
        raise SystemExit(f'{old_text!r}: esperado {expected}, encontrado {found}')
    s = s.replace(old_text, new_text)

if 'id="jc-actions"' not in s:
    raise SystemExit('jc-actions ausente')
if "state === 'idle'" not in s or 'onclick="gpsStart()"' not in s:
    raise SystemExit('botão iniciar ausente')
if 'S._autoTripsDataDate === d' in s:
    raise SystemExit('referência d inválida ainda presente')

p.write_text(s, encoding='utf-8')
Path('.tmp-journey-button.txt').unlink(missing_ok=True)
Path('.tmp-fix-journey-button.py').unlink(missing_ok=True)
Path('.github/workflows/inspect-journey-button.yml').unlink(missing_ok=True)
