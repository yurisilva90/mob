from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')

# 1) Stable per-date auto_trips cache: never let a transient empty refresh wipe a valid day.
old="""  if (S.autoTripsDate !== d) {
    const keepCurrent = S._autoTripsDataDate === d ? (S.autoTrips || []) : [];
    S.autoTripsDate = d;
    S.autoTrips = keepCurrent;
    loadAutoTripsForDay(d).then(list => {
      if (S.autoTripsDate !== d || !Array.isArray(list)) return; // erro mantém último dado válido
      S.autoTrips = list;
      S._autoTripsDataDate = d;
      renderJornada();
    });
  }
  day.autoTrips = S.autoTrips || [];
"""
new="""  // Cache por DATA. A Jornada é renderizada muitas vezes e as consultas são
  // assíncronas; um retorno vazio/transitório nunca pode apagar um conjunto
  // válido que já apareceu na tela (bug: km/R$/h apareciam e logo zeravam).
  S._autoTripsByDate = S._autoTripsByDate || {};
  if (S.autoTripsDate !== d) {
    const cachedDay = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : null;
    const keepCurrent = S._autoTripsDataDate === d ? (S.autoTrips || []) : [];
    S.autoTripsDate = d;
    S.autoTrips = cachedDay || keepCurrent;
    loadAutoTripsForDay(d).then(list => {
      if (S.autoTripsDate !== d || !Array.isArray(list)) return; // erro mantém último dado válido
      const prev = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : (S._autoTripsDataDate === d ? (S.autoTrips||[]) : []);
      // Consulta válida com dados sempre vence. Vazio só vence se nunca houve
      // dado válido para esse dia nesta sessão — evita flicker/zero por corrida
      // assíncrona ou réplica momentaneamente atrasada.
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
  day.autoTrips = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : (S.autoTrips || []);
"""
assert old in s, 'autoTrips render block not found'
s=s.replace(old,new,1)

# 2) Add consolidation helpers before renderJornada.
marker="function renderJornada() {"
assert marker in s, 'renderJornada marker missing'
helper=r'''
// Consolida captura automática + legado/importações sem contar a mesma corrida duas vezes.
// auto_trips é a fonte operacional principal; day.trips permanece apenas para registros
// antigos/manuais que ainda não têm correspondente automático.
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
s=s.replace(marker,helper+marker,1)

# 3) Revenue at top of Jornada uses consolidated sources.
old="""  const rev = day.trips.reduce((s,t)=>s+(t.value||0),0) + day.revenues.reduce((s,r)=>s+(r.amount||0),0)
            + day.autoTrips.reduce((s,t)=>s+(t.offer_value||0),0);
"""
new="""  const _journeySrc = journeyConsolidatedSources(day, day.autoTrips);
  const rev = _journeySrc.legacy.reduce((s,t)=>s+(t.value||0),0) + day.revenues.reduce((s,r)=>s+(r.amount||0),0)
            + _journeySrc.autos.reduce((s,t)=>s+(parseFloat(t.offer_value)||0),0);
"""
assert old in s, 'rev block not found'
s=s.replace(old,new,1)

# 4) In renderJourneyCard derive consolidated sources and stable readiness.
old="""  const autoTripsHoje = day.autoTrips || [];

  // Banner \"aguardando confirmação\""""
new="""  const autoTripsHoje = day.autoTrips || [];
  const journeySrc = journeyConsolidatedSources(day, autoTripsHoje);
  const legacyTripsHoje = journeySrc.legacy;
  const autoTripsReady = S._autoTripsDataDate === cardDate || Array.isArray(S._autoTripsByDate?.[cardDate]);

  // Banner \"aguardando confirmação\""""
assert old in s, 'autoTripsHoje block not found'
s=s.replace(old,new,1)

# 5) Make review card permanently available and support re-upload.
old="""    // Não interpreta cache ainda carregando como zero corridas. Durante refresh,
    // mantém o último estado visual válido do mesmo dia.
    const autoTripsReady = S._autoTripsDataDate === cardDate;
    if (autoTripsReady) {
      const pendingCount = autoTripsHoje.filter(t => t.status !== 'confirmada' || t.value_needs_review === true).length;
      pcbEl.dataset.dataDate = cardDate;
      if (pendingCount > 0) {
        pcbEl.style.display = 'flex';
        setText('pcb-title', pendingCount + (pendingCount===1 ? ' corrida aguardando confirmação' : ' corridas aguardando confirmação'));
      } else {
        pcbEl.style.display = 'none';
      }
    } else if (pcbEl.dataset.dataDate && pcbEl.dataset.dataDate !== cardDate) {
      pcbEl.style.display = 'none';
      pcbEl.dataset.dataDate = cardDate;
    }
"""
new="""    // Este card agora é também o caminho MANUAL permanente para revisar ou
    // reenviar vídeo de qualquer dia selecionado. Não depende de haver pendência.
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
"""
assert old in s, 'pending banner block not found'
s=s.replace(old,new,1)

# 6) KPI block uses consolidated sources; and never writes a transient zero while auto data is loading.
old="""  setText('jc-trips', day.trips.length + autoTripsHoje.length);
  setText('jc-trips2', day.trips.length + autoTripsHoje.length);
  const aceitasCount = day.trips.length + autoTripsHoje.length;
  const declinedCount = (S.declined || []).length;
  setText('jc-aceitas', aceitasCount);
  setText('jc-recusadas', declinedCount);
  const corridasSubEl = document.getElementById('jc-corridas-sub');
  if (corridasSubEl) corridasSubEl.style.display = (aceitasCount>0 || declinedCount>0) ? 'flex' : 'none';
  const kmAtivo = day.trips.reduce((s,t)=>s+(t.km||0),0)
                + autoTripsHoje.reduce((s,t)=>s+(parseFloat(t.real_km_trip ?? t.offer_km_trip)||0),0);
  const kmDesl = Math.max(0, totalKm - kmAtivo);
  setText('jc-kmativo', kmAtivo.toFixed(1));
  setText('jc-kmdesl', kmDesl.toFixed(1));
  const ganhosDia = day.trips.reduce((s,t)=>s+(t.value||0),0)
                  + autoTripsHoje.reduce((s,t)=>s+(t.offer_value||0),0);
  const horasDecimal = totalElapsed > 0 ? totalElapsed/3600 : 0;
  const rsh  = horasDecimal > 0 ? ganhosDia/horasDecimal : null;
  const rskm = totalKm > 0 ? ganhosDia/totalKm : null;
  setText('jc-rsh', rsh !== null ? DB.fRI(rsh) : 'R$0,00');
  setText('jc-rskm', rskm !== null ? DB.fRI(rskm) : 'R$0,00');
  setText('jc-rsh2', rsh !== null ? DB.fRI(rsh) : 'R$0,00');
  setText('jc-rskm2', rskm !== null ? DB.fRI(rskm) : 'R$0,00');
"""
new="""  // Só publica os KPIs dependentes de corridas depois que a fonte automática
  // está pronta. Isso impede o efeito \"mostra certo -> zera -> volta\".
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
    const kmAtivo = legacyTripsHoje.reduce((s,t)=>s+(parseFloat(t.km)||0),0)
                  + autoTripsHoje.reduce((s,t)=>s+(parseFloat(t.real_km_trip ?? t.offer_km_trip)||0),0);
    const kmDesl = Math.max(0, totalKm - kmAtivo);
    setText('jc-kmativo', kmAtivo.toFixed(1));
    setText('jc-kmdesl', kmDesl.toFixed(1));
    const ganhosDia = legacyTripsHoje.reduce((s,t)=>s+(parseFloat(t.value)||0),0)
                    + autoTripsHoje.reduce((s,t)=>s+(parseFloat(t.offer_value)||0),0);
    const horasDecimal = totalElapsed > 0 ? totalElapsed/3600 : 0;
    rsh  = horasDecimal > 0 ? ganhosDia/horasDecimal : null;
    rskm = totalKm > 0 ? ganhosDia/totalKm : null;
    setText('jc-rsh', rsh !== null ? DB.fRI(rsh) : 'R$0,00');
    setText('jc-rskm', rskm !== null ? DB.fRI(rskm) : 'R$0,00');
    setText('jc-rsh2', rsh !== null ? DB.fRI(rsh) : 'R$0,00');
    setText('jc-rskm2', rskm !== null ? DB.fRI(rskm) : 'R$0,00');
  }
"""
assert old in s, 'KPI block not found'
s=s.replace(old,new,1)

# 7) After video reconciliation, clear only that day's stable cache and reload it.
old="""  if (toUpdateAuto.length || toPushAuto.length) { S.autoTripsDate = null; } // força recarregar no próximo renderJornada
"""
new="""  if (toUpdateAuto.length || toPushAuto.length) {
    S._autoTripsByDate = S._autoTripsByDate || {};
    delete S._autoTripsByDate[S.curDate];
    S.autoTripsDate = null;
    S._autoTripsDataDate = null;
    setTimeout(() => { try { renderJornada(); } catch(e) {} }, 700); // dá tempo da escrita concluir antes do reload
  }
"""
assert old in s, 'confirmImport cache reset not found'
s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')
print('journey consolidation/review patch applied')
