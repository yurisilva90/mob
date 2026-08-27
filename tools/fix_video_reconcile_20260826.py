from pathlib import Path
import re
p=Path('index.html')
s=p.read_text()
# 1) Make confirmImport await persistence before refreshing UI.
old=re.compile(r"  // Aplica as atualizações nas automáticas casadas.*?  window\._pendingImportVideoIds = null;\n  if \(toUpdateAuto\.length \|\| toPushAuto\.length\) \{ S\.autoTripsDate = null; \}[^\n]*",re.S)
m=old.search(s)
if not m:
    raise SystemExit('confirmImport persistence block not found')
new="""  // Persiste toda a reconciliação antes de atualizar Jornada/Corridas/Financeiro.
  const importWrites = [];
  toUpdateAuto.forEach(u => {
    importWrites.push(_SUPA.from('auto_trips').update({
      offer_value: u.value,
      real_km_trip: u.km > 0 ? u.km : undefined,
      dinheiro: u.dinheiro,
      status: 'confirmada',
      value_needs_review: false,
      data_quality_flag: null,
      import_video_id: videoId || undefined,
      platform_history_at: u.historyAt || undefined,
      observation: 'Confirmada/reconciliada pelo histórico em vídeo; dados operacionais preservados.'
    }).eq('id', u.id).then(({error}) => { if (error) throw error; }));
  });
  if (toPushAuto.length) {
    importWrites.push(_SUPA.from('auto_trips').insert(toPushAuto).then(({error}) => { if (error) throw error; }));
  }
  if (videoId) {
    importWrites.push(_SUPA.from('import_videos').update({ trip_count: toUpdateAuto.length + toPushAuto.length }).eq('id', videoId)
      .then(({error}) => { if (error) console.warn('trip_count import_videos:', error); }));
  }
  try { await Promise.all(importWrites); }
  catch (e) {
    console.error('confirmImport persist:', e);
    showToast('Não consegui salvar toda a revisão. Tente confirmar novamente.', 'error');
    return;
  }
  window._pendingImportVideoIds = null;
  if (toUpdateAuto.length || toPushAuto.length) {
    S.autoTripsDate = null; S._autoTripsDataDate = null; S.autoTrips = [];
    try {
      const fresh = await loadAutoTripsForDay(S.curDate);
      if (Array.isArray(fresh)) { S.autoTrips=fresh; S.autoTripsDate=S.curDate; S._autoTripsDataDate=S.curDate; }
    } catch(e) { console.warn('refresh pos revisao:',e); }
    if (typeof _finAuto !== 'undefined') _finAuto={key:'',byDate:{},loading:false,ts:0};
  }"""
s=s[:m.start()]+new+s[m.end():]
# 2) Strengthen frame-level dedupe: same platform/day/time is one history ride; keep richest candidate.
# Inject helper immediately before confirmImport if absent.
if 'function dedupeVideoHistoryTrips' not in s:
    anchor='async function confirmImport('
    i=s.find(anchor)
    if i<0: raise SystemExit('confirmImport anchor not found')
    helper="""function dedupeVideoHistoryTrips(rows){
  const out=new Map();
  for(const r of (rows||[])){
    const plat=String(r.platform||r.plat||'').toLowerCase();
    const date=String(r.date||r.data||S.curDate||'');
    const time=String(r.time||r.hora||'').slice(0,5);
    // Itens financeiros não são corridas.
    const label=String(r.type||r.kind||r.label||r.description||'').toLowerCase();
    if(/recompensa|bonus|bônus|compensa|taxa|debito|débito|ajuste|incentivo/.test(label)) continue;
    const key=plat+'|'+date+'|'+time;
    const score=x=>[x.origin,x.origin_address,x.dest,x.dest_address].filter(Boolean).join(' ').length + (Number(x.km||0)>0?20:0);
    const prev=out.get(key);
    if(!prev || score(r)>score(prev)) out.set(key,r);
  }
  return [...out.values()];
}

"""
    s=s[:i]+helper+s[i:]
# 3) Apply dedupe to common pending import assignment if recognizable.
for pat in [r"(const\s+imported\s*=\s*)([^;]+);",r"(let\s+imported\s*=\s*)([^;]+);"]:
    mm=re.search(pat,s)
    if mm and 'dedupeVideoHistoryTrips' not in mm.group(2):
        s=s[:mm.start()]+mm.group(1)+'dedupeVideoHistoryTrips('+mm.group(2)+');'+s[mm.end():]
        break
p.write_text(s)
print('patched video reconciliation')
