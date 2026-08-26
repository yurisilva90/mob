from pathlib import Path
s=Path('index.html').read_text(encoding='utf-8')
terms=['function gpsStart','function gpsStop','function restoreGpsSession','function gpsUpdate','sm_gps_session','checkpoint','elapsed_secs','from(\'sessions\')','upsert({id:g.sessionId']
out=[]
for term in terms:
    start=0
    while True:
        i=s.find(term,start)
        if i<0: break
        out.append(f'\n===== {term} @ {i} =====\n')
        out.append(s[max(0,i-2500):min(len(s),i+7000)])
        start=i+1
Path('_journey_functions_probe.txt').write_text(''.join(out),encoding='utf-8')
