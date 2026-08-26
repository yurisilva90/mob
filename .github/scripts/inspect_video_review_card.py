from pathlib import Path
s=Path('index.html').read_text(encoding='utf-8')
terms=['vídeo','video','revisar corridas','revisão','conferência','importar corridas','#F59E0B','#F97316','orange','laranja','upload']
out=[]
seen=set()
for term in terms:
    start=0
    while True:
        i=s.lower().find(term.lower(),start)
        if i<0: break
        key=i//500
        if key not in seen:
            seen.add(key)
            out.append(f'\n===== {term} @ {i} =====\n')
            out.append(s[max(0,i-3500):min(len(s),i+6500)])
        start=i+1
Path('_video_review_card_probe.txt').write_text(''.join(out),encoding='utf-8')
