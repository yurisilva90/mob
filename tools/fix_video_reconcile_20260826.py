from pathlib import Path
import re
p=Path('index.html')
s=p.read_text()
start=s.find('  // Aplica as atualizações nas automáticas casadas')
end=s.find('  DB.saveDay(day); closeMo(\'mo-import-confirm\'); window._pendingTrips=null;',start)
if start<0 or end<0: raise SystemExit('confirmImport persistence anchors not found')
new="""  // Persiste TODAS as gravações antes de redesenhar. Evita a tela reler a fotografia antiga.
  const importWrites = [];
  toUpdateAuto.forEach(u => {
    importWrites.push(_SUPA.from('auto_trips').update({
      offer_value: u.value,
      real_km_trip: u.km > 0 ? u.km : undefined,
      dinheiro: u.dinheiro,
      status: 'confirmada', value_needs_review: false, data_quality_flag: null,
      import_video_id: videoId || undefined,
      observation: 'Valor confirmado/reconciliado pelo histórico em vídeo; dados operacionais preservados.'
    }).eq('id',u.id).then(({error})=>{if(error) throw error;}));
  });
  if(toPushAuto.length) importWrites.push(_SUPA.from('auto_trips').insert(toPushAuto).then(({error})=>{if(error) throw error;}));
  if(videoId) importWrites.push(_SUPA.from('import_videos').update({trip_count:toUpdateAuto.length+toPushAuto.length}).eq('id',videoId));
  try { await Promise.all(importWrites); }
  catch(e){ console.error('confirmImport persist',e); showToast('Falha ao salvar a revisão. Tente confirmar novamente.','error'); return; }
  window._pendingImportVideoIds=null;
  if(toUpdateAuto.length||toPushAuto.length){
    S._autoTripsByDate=S._autoTripsByDate||{}; delete S._autoTripsByDate[S.curDate];
    S.autoTripsDate=null; S._autoTripsDataDate=null; S.autoTrips=[];
    try { const fresh=await loadAutoTripsForDay(S.curDate); if(Array.isArray(fresh)){S.autoTrips=fresh;S.autoTripsDate=S.curDate;S._autoTripsDataDate=S.curDate;} } catch(e){}
    if(typeof _finAuto!=='undefined') _finAuto={key:'',byDate:{},loading:false,ts:0};
  }
"""
s=s[:start]+new+s[end:]
# O resolvedUnique já garante uma corrida por plataforma+horário. Acrescenta filtro de lançamento financeiro
# para leituras sem rota: valores pequenos isolados (ex. recompensa R$1,10) não viram corrida.
needle='  const resolvedUnique = resolveTimeConflicts(unique);\n  unique.length = 0;\n  unique.push(...resolvedUnique);'
if needle not in s: raise SystemExit('resolvedUnique anchor not found')
replacement="""  const resolvedUnique = resolveTimeConflicts(unique);
  // A 99 exibe recompensa/compensação/taxa no mesmo histórico. Um valor isolado sem
  // km, duração ou endereços é lançamento financeiro, não corrida. Mantém separado
  // para não inflar quantidade/receita de corridas.
  const financialOnly = resolvedUnique.filter(t => {
    const label=String(t.type||t.kind||t.label||t.description||'').toLowerCase();
    const explicit=/recompensa|bonus|bônus|compensa|taxa|debito|débito|ajuste|incentivo/.test(label);
    const noRoute=!(Number(t.km||0)>0) && !(Number(t.duration||0)>0) && !t.originFull && !t.destFull;
    return explicit || (t.platform==='99' && Number(t.value||0)>0 && Number(t.value||0)<3 && noRoute);
  });
  const rideOnly = resolvedUnique.filter(t => !financialOnly.includes(t));
  unique.length = 0;
  unique.push(...rideOnly);
  // Persiste os lançamentos reconhecidos separadamente; nunca em auto_trips.
  if(_supaUser && financialOnly.length){
    for(const f of financialOnly){
      const opDate=window._pendingImportOperationalDate||S.curDate||DB.today();
      let ms=operationalTimestampForTime(f.platform||operationalPlat,opDate,f.time||'00:00');
      const label=String(f.type||f.kind||f.label||f.description||'').toLowerCase();
      const debit=/taxa|debito|débito/.test(label);
      const typ=/recompensa|bonus|bônus|incentivo/.test(label)?'reward':(/compensa/.test(label)?'compensation':(debit?'fee':'adjustment'));
      await _SUPA.from('platform_transactions').insert({user_id:_supaUser.id,platform:f.platform==='99'?'99':'uber',occurred_at:new Date(ms||Date.now()).toISOString(),operational_date:opDate,transaction_type:typ,raw_label:f.label||f.description||'Lançamento identificado no vídeo',amount:Math.abs(Number(f.value||0)),direction:debit?'debit':'credit',reconciliation_status:'confirmed',observation:'Identificado separadamente na revisão por vídeo.',raw_payload:{source:'video_review'}}).then(()=>{}).catch(()=>{});
    }
  }"""
s=s.replace(needle,replacement,1)
p.write_text(s)
print('patched current importer')
