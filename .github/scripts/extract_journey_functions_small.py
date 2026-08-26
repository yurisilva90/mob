from pathlib import Path
s=Path('index.html').read_text(encoding='utf-8')

def extract_function(name):
    sig='function '+name
    i=s.find(sig)
    if i<0: return f'\nMISSING {name}\n'
    b=s.find('{',i)
    depth=0; quote=None; esc=False; j=b
    while j<len(s):
        c=s[j]
        if quote:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c==quote: quote=None
        else:
            if c in "'\"`": quote=c
            elif c=='{': depth+=1
            elif c=='}':
                depth-=1
                if depth==0: return '\n===== '+name+' =====\n'+s[i:j+1]
        j+=1
    return '\nBROKEN '+name+'\n'

out=[]
for n in ['loadAutoTripsForDay','renderJourneyCard','confirmImport','openImportModal','startImportVideo','processImportVideo','renderJornada']:
    x=extract_function(n)
    if len(x)>45000: x=x[:45000]+'\n...[TRUNCATED]...'
    out.append(x)
# snippets around key text
for term in ['pending-confirm-banner','Importar corridas','Revisar corridas','import-video','import_videos','type="file"','accept="video']:
    i=s.find(term)
    out.append(f'\n===== TERM {term} @ {i} =====\n')
    if i>=0: out.append(s[max(0,i-4000):min(len(s),i+10000)])
Path('_journey_functions_small.txt').write_text(''.join(out),encoding='utf-8')
