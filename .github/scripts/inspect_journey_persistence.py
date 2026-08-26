from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')
terms=['nativeSyncGps','restoreSession','startJourney','startJornada','sessions','elapsed_secs','syncSession','saveSession','Jornada reiniciada','reiniciada']
out=[]
for term in terms:
    i=s.find(term)
    out.append(f'\n===== {term} @ {i} =====\n')
    if i>=0:
        out.append(s[max(0,i-3500):min(len(s),i+8000)])
Path('_journey_persistence_probe.txt').write_text(''.join(out),encoding='utf-8')
