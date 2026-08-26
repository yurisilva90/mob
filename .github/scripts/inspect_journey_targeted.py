from pathlib import Path
s=Path('index.html').read_text(encoding='utf-8')
out=[]
def one(term,before=2500,after=12000,start=0):
    i=s.find(term,start)
    out.append(f'\n===== {term} @ {i} =====\n')
    if i>=0: out.append(s[max(0,i-before):min(len(s),i+after)])
    return i
one('function renderJornada')
one("from('auto_trips')")
one('auto_trips')
one('function loadAutoTrips')
one('function confirmImport')
one('import_videos')
one('Revisar corridas')
one('Importar corridas')
one('function renderVideo')
one('uploadVideo')
one('videoFile')
one('file-input')
Path('_journey_targeted_probe.txt').write_text(''.join(out),encoding='utf-8')
