from pathlib import Path
s=Path('index.html').read_text(encoding='utf-8')
terms=['function renderJornada','auto_trips','loadAutoTrips','from(\'auto_trips\')','from("auto_trips")','import_videos','confirmImport','Revisar corridas','Importar corridas','video','upload','renderHome','day.trips','trips =','S.autoTrips']
out=[]
seen=set()
for term in terms:
    start=0
    while True:
        i=s.find(term,start)
        if i<0: break
        k=(i//1200,term)
        if k not in seen:
            seen.add(k)
            out.append(f'\n===== {term} @ {i} =====\n')
            out.append(s[max(0,i-5000):min(len(s),i+12000)])
        start=i+1
Path('_journey_consolidation_probe.txt').write_text(''.join(out),encoding='utf-8')
