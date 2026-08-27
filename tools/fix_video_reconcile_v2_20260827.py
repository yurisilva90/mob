from pathlib import Path
import re
p=Path('index.html'); s=p.read_text(encoding='utf-8'); orig=s

# Preserve multiple legitimate rides sharing HH:mm; exact time+value duplicates are merged.
pat=r"function\s+resolveTimeConflicts\s*\(list\)\s*\{.*?\n\s*\}\s*\n\s*function\s+applyDetails"
rep='''function resolveTimeConflicts(list) {
      const out=[];
      for(const raw of (list||[])){
        const t=normalizeTime(raw&&raw.time), v=round2(Number(raw&&raw.value)||0);
        if(!t||v<=0) continue;
        const pay=String(raw&&(raw.payment_method||raw.payment)||'').toLowerCase();
        const cat=String(raw&&(raw.category||raw.service)||'').toLowerCase();
        const dup=out.find(x=>normalizeTime(x.time)===t && Math.abs((Number(x.value)||0)-v)<0.01 && (!pay||!String(x.payment_method||x.payment||'').toLowerCase()||String(x.payment_method||x.payment||'').toLowerCase()===pay) && (!cat||!String(x.category||x.service||'').toLowerCase()||String(x.category||x.service||'').toLowerCase()===cat));
        if(dup){ mergeFields(dup,raw); dup._enriched=!!(dup._enriched||raw._enriched); }
        else out.push({...raw,time:t,value:v});
      }
      return out.sort((a,b)=>timeToMinutes(b.time)-timeToMinutes(a.time));
    }

    function applyDetails'''
s,n=re.subn(pat,rep,s,count=1,flags=re.S)
print('resolver replacements',n)

needle='Não repita a mesma corrida em frames diferentes.'
extra="""Não repita a mesma corrida em frames diferentes. RECONCILIAÇÃO OBRIGATÓRIA DO VÍDEO: trate o vídeo como sequência temporal de uma lista rolável, não como imagens independentes. Reconstrua primeiro os CARDS e acompanhe o mesmo card entre frames por posição/movimento do scroll + horário + valor + pagamento + categoria + origem/destino. Card parcial em um frame e completo no seguinte deve ser MESCLADO, preservando a leitura mais completa. HH:mm NÃO é identificador único: duas corridas podem ocorrer no mesmo minuto; se valor, pagamento, categoria ou rota diferirem, mantenha ambas. Nunca copie o horário de card vizinho quando o horário não estiver visível. Ordene pelo horário textual do histórico, nunca pela ordem dos frames. Faça reconciliação global antes da resposta. 'Outro', ajustes, taxas, créditos/débitos e especialmente valores negativos NÃO são corridas. Normalize R$, vírgula/ponto, abreviações e pequenas variações de endereço. Só devolva corrida com value > 0 e evidência visual de card de corrida. Preserve app/dinheiro. Em conflito, escolha a leitura com maior evidência e completude."""
if needle in s: s=s.replace(needle,extra,1); print('prompt patched')
else: print('prompt already changed or needle absent')

old='const candidate = unique.find(t => normalizeTime(t.time) === dt && !t._enriched);'
new="""const sameTimeCandidates=unique.filter(t=>normalizeTime(t.time)===dt&&!t._enriched);
          const dv=round2(Number(d.value||d.fare||0)), dpay=String(d.payment_method||d.payment||'').toLowerCase(), dcat=String(d.category||d.service||'').toLowerCase();
          const candidate=sameTimeCandidates.map(t=>{let score=0;const tv=round2(Number(t.value||0));if(dv>0&&Math.abs(tv-dv)<0.01)score+=100;else if(dv>0)score-=50;const tp=String(t.payment_method||t.payment||'').toLowerCase(),tc=String(t.category||t.service||'').toLowerCase();if(dpay&&tp&&dpay===tp)score+=25;if(dcat&&tc&&dcat===tc)score+=15;return{t,score}}).sort((a,b)=>b.score-a.score)[0]?.t||null;"""
if old in s: s=s.replace(old,new,1); print('detail matcher patched')
else: print('detail matcher already changed or needle absent')

if 'VIDEO_RECONCILE_V2' not in s:
    marker='let videoImportState ='
    if marker in s: s=s.replace(marker,"const VIDEO_RECONCILE_V2='2026-08-27';\n  "+marker,1)

if s!=orig:
    p.write_text(s,encoding='utf-8'); print('video reconcile v2 applied')
else:
    print('video reconcile v2 already applied; validating existing code')
# idempotent trigger 6
