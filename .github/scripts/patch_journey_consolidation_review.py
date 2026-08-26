from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')

def replace_range(text,start_marker,end_marker,new,include_end=True,start_at=0):
    a=text.find(start_marker,start_at)
    assert a>=0, f'start marker not found: {start_marker[:80]}'
    b=text.find(end_marker,a)
    assert b>=0, f'end marker not found: {end_marker[:80]}'
    if include_end: b+=len(end_marker)
    return text[:a]+new+text[b:]

# 1) cache estável por data
if '_autoTripsByDate[d]' not in s:
    new_auto="""  // Cache por DATA. Um refresh assíncrono vazio nunca apaga dados válidos
  // que já apareceram na Jornada (corrige o efeito mostra -> zera).
  S._autoTripsByDate = S._autoTripsByDate || {};
  if (S.autoTripsDate !== d) {
    const cachedDay = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : null;
    const keepCurrent = S._autoTripsDataDate === d ? (S.autoTrips || []) : [];
    S.autoTripsDate = d;
    S.autoTrips = cachedDay || keepCurrent;
    loadAutoTripsForDay(d).then(list => {
      if (S.autoTripsDate !== d || !Array.isArray(list)) return;
      const prev = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : (S._autoTripsDataDate === d ? (S.autoTrips||[]) : []);
      const stable = (list.length === 0 && prev.length > 0) ? prev : list;
      S._autoTripsByDate[d] = stable;
      S.autoTrips = stable;
      S._autoTripsDataDate = d;
      renderJornada();
    });
  } else if (Array.isArray(S._autoTripsByDate[d])) {
    S.autoTrips = S._autoTripsByDate[d];
    S._autoTripsDataDate = d;
  }
  day.autoTrips = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : (S.autoTrips || []);"""
    s=replace_range(s,"  if (S.autoTripsDate !== d) {","  day.autoTrips = S.autoTrips || [];",new_auto)

# 2) helpers de consolidação
if 'function journeyConsolidatedSources' not in s:
    marker='function renderJornada() {'
    i=s.find(marker); assert i>=0
    helper=r'''
// Consolida captura automática + legado/importações sem contar a mesma corrida duas vezes.
function _journeyPlat(v) {
  v=String(v||'').toLowerCase();
  return v.includes('99') ? '99' : (v.includes('uber') ? 'uber' : v);
}
function _journeyNormAddr(v) {
  return String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase()
    .replace(/\b(rua|r\.?|avenida|av\.?|estrada|travessa|rodovia)\b/g,'')
    .replace(/[^a-z0-9]+/g,' ').trim().slice(0,42);
}
function _journeyLegacyMinute(t) {
  const m=String(t?.time||'').match(/(\d{1,2}):(\d{2})/); return m ? (+m[1])*60+(+m[2]) : null;
}
function _journeyAutoMinute(t) {
  const raw=t?.trip_started_at||t?.accepted_at||t?.platform_history_at; if(!raw) return null;
  const d=new Date(raw); return isNaN(d) ? null : d.getHours()*60+d.getMinutes();
}
function _journeyTripsLikelySame(l,a) {
  if (_journeyPlat(l?.platform)!==_journeyPlat(a?.platform)) return false;
  if (l?.platform_transaction_id && a?.platform_transaction_id && l.platform_transaction_id===a.platform_transaction_id) return true;
  const lm=_journeyLegacyMinute(l), am=_journeyAutoMinute(a);
  const dt=(lm!=null&&am!=null)?Math.abs(lm-am):999;
  const lv=parseFloat(l?.value)||0, av=parseFloat(a?.offer_value)||0;
  const valueClose=lv>0&&av>0&&Math.abs(lv-av)<=0.06;
  const lo=_journeyNormAddr(l?.origin_full||l?.origin), ao=_journeyNormAddr(a?.origin_address||a?.gps_origin_address);
  const ld=_journeyNormAddr(l?.dest_full||l?.dest), ad=_journeyNormAddr(a?.dest_address||a?.gps_dest_address);
  const originClose=lo.length>=6&&ao.length>=6&&(lo.includes(ao)||ao.includes(lo)||lo.slice(0,16)===ao.slice(0,16));
  const destClose=ld.length>=6&&ad.length>=6&&(ld.includes(ad)||ad.includes(ld)||ld.slice(0,16)===ad.slice(0,16));
  return (dt<=12 && (valueClose||originClose||destClose)) || (dt<=30 && originClose && destClose);
}
function journeyConsolidatedSources(day, autoTrips) {
  const autos=Array.isArray(autoTrips)?autoTrips:[];
  const legacy=(day?.trips||[]).filter(l=>!autos.some(a=>_journeyTripsLikelySame(l,a)));
  return { legacy, autos, count:legacy.length+autos.length };
}

'''
    s=s[:i]+helper+s[i:]

# 3) receita consolidada no topo
if 'const _journeySrc = journeyConsolidatedSources(day, day.autoTrips);' not in s:
    a=s.find('  const rev = day.trips.reduce'); assert a>=0
    b=s.find('  const exp =',a); assert b>=0
    s=s[:a]+"""  const _journeySrc = journeyConsolidatedSources(day, day.autoTrips);
  const rev = _journeySrc.legacy.reduce((sum,t)=>sum+(parseFloat(t.value)||0),0) + day.revenues.reduce((sum,r)=>sum+(r.amount||0),0)
            + _journeySrc.autos.reduce((sum,t)=>sum+(parseFloat(t.offer_value)||0),0);
"""+s[b:]

# 4) fontes consolidadas dentro do card
needle='  const autoTripsHoje = day.autoTrips || [];'
pos=s.find(needle); assert pos>=0
if 'const journeySrc = journeyConsolidatedSources(day, autoTripsHoje);' not in s[pos:pos+800]:
    ins=needle+"\n  const journeySrc = journeyConsolidatedSources(day, autoTripsHoje);\n  const legacyTripsHoje = journeySrc.legacy;\n  const autoTripsReady = S._autoTripsDataDate === cardDate || Array.isArray(S._autoTripsByDate?.[cardDate]);"
    s=s[:pos]+s[pos:].replace(needle,ins,1)

# 5) card de revisão sempre disponível, inclusive reenvio
banner_pos=s.find("  const pcbEl = document.getElementById('pending-confirm-banner');")
assert banner_pos>=0
if 'pcb-review-btn' not in s[banner_pos:banner_pos+5000]:
    if_start=s.find('  if (pcbEl) {',banner_pos); assert if_start>=0
    end_marker='\n\n  // Barra Online/Buscando passageiro/Em corrida'
    if_end=s.find(end_marker,if_start); assert if_end>=0
    new_if="""  if (pcbEl) {
    pcbEl.dataset.dataDate = cardDate;
    pcbEl.style.display = 'flex';
    const pendingCount = autoTripsReady ? autoTripsHoje.filter(t => t.status !== 'confirmada' || t.value_needs_review === true).length : null;
    setText('pcb-title', pendingCount > 0
      ? pendingCount + (pendingCount===1 ? ' corrida aguardando confirmação' : ' corridas aguardando confirmação')
      : 'Revisar corridas por vídeo');
    let reviewBtn = pcbEl.querySelector('.pcb-review-btn');
    if (!reviewBtn) {
      reviewBtn = document.createElement('button');
      reviewBtn.type='button'; reviewBtn.className='pcb-review-btn';
      reviewBtn.style.cssText='margin-left:auto;border:0;background:#fff;color:#B45309;border-radius:10px;padding:8px 10px;font-size:11px;font-weight:800;white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,.08)';
      pcbEl.appendChild(reviewBtn);
    }
    reviewBtn.textContent = pendingCount > 0 ? 'Enviar vídeo' : 'Revisar novamente';
    reviewBtn.onclick = (ev) => { ev.stopPropagation(); openImportPrecheck(); };
    pcbEl.onclick = () => openImportPrecheck();
  }"""
    s=s[:if_start]+new_if+s[if_end:]

# 6) KPIs consolidados e sem zero transitório
kpi_start=s.find("  setText('jc-trips',",banner_pos); assert kpi_start>=0
kpi_end=s.find('  // Cor por indicador',kpi_start); assert kpi_end>=0
if 'canPublishTripKpis' not in s[kpi_start:kpi_end]:
    new_kpi="""  // Só publica KPIs dependentes de corridas depois que a fonte automática está pronta.
  const canPublishTripKpis = autoTripsReady || legacyTripsHoje.length > 0;
  const declinedCount = (S.declined || []).length;
  let rsh = null, rskm = null;
  if (canPublishTripKpis) {
    const aceitasCount = journeySrc.count;
    setText('jc-trips', aceitasCount);
    setText('jc-trips2', aceitasCount);
    setText('jc-aceitas', aceitasCount);
    setText('jc-recusadas', declinedCount);
    const corridasSubEl = document.getElementById('jc-corridas-sub');
    if (corridasSubEl) corridasSubEl.style.display = (aceitasCount>0 || declinedCount>0) ? 'flex' : 'none';
    const kmAtivo = legacyTripsHoje.reduce((sum,t)=>sum+(parseFloat(t.km)||0),0)
                  + autoTripsHoje.reduce((sum,t)=>sum+(parseFloat(t.real_km_trip ?? t.offer_km_trip)||0),0);
    const kmDesl = Math.max(0, totalKm - kmAtivo);
    setText('jc-kmativo', kmAtivo.toFixed(1));
    setText('jc-kmdesl', kmDesl.toFixed(1));
    const ganhosDia = legacyTripsHoje.reduce((sum,t)=>sum+(parseFloat(t.value)||0),0)
                    + autoTripsHoje.reduce((sum,t)=>sum+(parseFloat(t.offer_value)||0),0);
    const horasDecimal = totalElapsed > 0 ? totalElapsed/3600 : 0;
    rsh  = horasDecimal > 0 ? ganhosDia/horasDecimal : null;
    rskm = totalKm > 0 ? ganhosDia/totalKm : null;
    setText('jc-rsh', rsh !== null ? DB.fRI(rsh) : 'R$0,00');
    setText('jc-rskm', rskm !== null ? DB.fRI(rskm) : 'R$0,00');
    setText('jc-rsh2', rsh !== null ? DB.fRI(rsh) : 'R$0,00');
    setText('jc-rskm2', rskm !== null ? DB.fRI(rskm) : 'R$0,00');
  }
"""
    s=s[:kpi_start]+new_kpi+s[kpi_end:]

# 7) após conciliação por vídeo, invalida somente o dia revisado e recarrega
old="  if (toUpdateAuto.length || toPushAuto.length) { S.autoTripsDate = null; } // força recarregar no próximo renderJornada"
if old in s:
    s=s.replace(old,"""  if (toUpdateAuto.length || toPushAuto.length) {
    S._autoTripsByDate = S._autoTripsByDate || {};
    delete S._autoTripsByDate[S.curDate];
    S.autoTripsDate = null;
    S._autoTripsDataDate = null;
    setTimeout(() => { try { renderJornada(); } catch(e) {} }, 700);
  }""",1)

p.write_text(s,encoding='utf-8')
print('journey consolidation/review patch applied')
