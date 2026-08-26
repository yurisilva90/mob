from pathlib import Path
s=Path('index.html').read_text(encoding='utf-8')
terms=['function renderJornada','renderJornada =','auto_trips','loadAuto','syncCloud','hydrate','R$/hora','porHora','total do dia','sessions']
out=[]; seen=set()
for term in terms:
    start=0
    while True:
        i=s.lower().find(term.lower(),start)
        if i<0: break
        key=i//700
        if key not in seen:
            seen.add(key)
            out.append(f'\n===== {term} @ {i} =====\n')
            out.append(s[max(0,i-5000):min(len(s),i+10000)])
        start=i+1
Path('_journey_zero_flicker_probe.txt').write_text(''.join(out),encoding='utf-8')
