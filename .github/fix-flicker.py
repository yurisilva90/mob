from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')

# 1) Banner estável: só muda quando auto_trips daquele dia estiver carregado.
old = """  const pcbEl = document.getElementById('pending-confirm-banner');
  if (pcbEl) {
    const pendingCount = autoTripsHoje.filter(t => t.status === 'capturada' || t.status === 'estimada').length;
    if (pendingCount > 0) {
      pcbEl.style.display = 'flex';
      setText('pcb-title', pendingCount + (pendingCount===1 ? ' corrida aguardando confirmação' : ' corridas aguardando confirmação'));
    } else {
      pcbEl.style.display = 'none';
    }
  }
"""
new = """  const pcbEl = document.getElementById('pending-confirm-banner');
  if (pcbEl) {
    // Não interpreta cache ainda carregando como zero corridas. Durante refresh,
    // mantém o último estado visual válido do mesmo dia.
    const autoTripsReady = S._autoTripsDataDate === d;
    if (autoTripsReady) {
      const pendingCount = autoTripsHoje.filter(t => t.status === 'capturada' || t.status === 'estimada').length;
      pcbEl.dataset.dataDate = d;
      if (pendingCount > 0) {
        pcbEl.style.display = 'flex';
        setText('pcb-title', pendingCount + (pendingCount===1 ? ' corrida aguardando confirmação' : ' corridas aguardando confirmação'));
      } else {
        pcbEl.style.display = 'none';
      }
    } else if (pcbEl.dataset.dataDate && pcbEl.dataset.dataDate !== d) {
      pcbEl.style.display = 'none';
      pcbEl.dataset.dataDate = d;
    }
  }
"""
assert old in s, 'banner block not found'
s = s.replace(old, new, 1)

# 2) A renderização base não escreve mais nas barras; a timeline V3 é a dona.
old = """  const jcBd = document.getElementById('jc-breakdown');
  if (jcBd) {
    if (live && liveElapsed > 0) {
      jcBd.style.display = '';
      const liveAutoTrips = autoTripsHoje.filter(t => {
        const ts = autoTripTs(t);
        return ts && ts >= g.start;
      });
      const bd = computeStatusBreakdown(liveElapsed, liveKm, liveAutoTrips);
      setHTML('jc-bar', buildSbarHtml(bd));
      setHTML('jc-blist', buildSrowsHtml(bd));
    } else {
      jcBd.style.display = 'none';
    }
  }

  // Mesma barra, agora no card \"Total do dia\" — soma o dia inteiro
  // (sessões encerradas + sessão ao vivo), então funciona em qualquer
  // data, passada ou de hoje, não só enquanto a jornada está rodando.
  const tdBdRow = document.getElementById('td-bd-row');
  if (tdBdRow) {
    if (totalElapsed > 0) {
      tdBdRow.style.display = '';
      const tdBd = computeStatusBreakdown(totalElapsed, totalKm, autoTripsHoje);
      setHTML('td-bd-bar', buildSbarHtml(tdBd));
      setHTML('td-bd-list', buildSrowsHtml(tdBd));
    } else {
      tdBdRow.style.display = 'none';
    }
  }
"""
new = """  // As barras são atualizadas exclusivamente pela timeline contínua V3.
  // A rotina base não sobrescreve mais a leitura real com auto_trips.
  const jcBd = document.getElementById('jc-breakdown');
  const tdBdRow = document.getElementById('td-bd-row');
"""
assert old in s, 'legacy bars block not found'
s = s.replace(old, new, 1)

# 3) Desliga a rotina V2 concorrente (mantém função exposta para compatibilidade).
old = """  window.renderStatusTimeline=renderStatusTimeline;

  if(typeof window.renderJornada==='function'){
    const original=window.renderJornada;
    window.renderJornada=function(){
      const r=original.apply(this,arguments);
      setTimeout(renderStatusTimeline,0);
      return r;
    };
  }
  setInterval(renderStatusTimeline,1000);
  setInterval(()=>{ if(S&&S.sec==='jornada'&&S.curDate) loadStatusSegments(S.curDate); },15000);
  setTimeout(renderStatusTimeline,500);
"""
new = """  // Compatibilidade apenas: V3 abaixo é o único renderizador automático.
  window.renderStatusTimeline=renderStatusTimeline;
"""
assert old in s, 'V2 auto hook not found'
s = s.replace(old, new, 1)

marker = '<!-- JOURNEY_CONTINUOUS_OPERATIONAL_V3 -->'
pos = s.index(marker)
head, v3 = s[:pos], s[pos:]

# 4) Respostas assíncronas atualizam apenas lista/barras contínuas.
v3 = v3.replace(
    "try{ if(S.sec==='jornada') setTimeout(()=>renderJornada(),0); }catch(e){}",
    "try{ if(S.sec==='jornada') setTimeout(()=>{renderContinuousSessionList();renderContinuousStatusBars();},0); }catch(e){}"
)
v3 = v3.replace(
    "try{if(S.sec==='jornada')setTimeout(()=>renderJornada(),0);}catch(e){}",
    "try{if(S.sec==='jornada')setTimeout(()=>{renderContinuousSessionList();renderContinuousStatusBars();},0);}catch(e){}"
)

# 5) Primeira carga nunca vira 100% Online por fallback.
old = """  window.journeyBreakdownForSession = function(sess,elapsedSec,kmTotal,fallbackAuto){
    if(!sess?.id) return computeStatusBreakdown(elapsedSec,kmTotal,fallbackAuto||[]);
    ensureJourneyStatus(sess);
    const c=journeyStatusCache.get(journeyKey(sess));
    if(c&&c.rows&&c.rows.length) return statusBreakdownRows(c.rows,elapsedSec,kmTotal,null,null,(S?.gps?.st==='running'?S.gps.sessionId:null));
    return computeStatusBreakdown(elapsedSec,kmTotal,fallbackAuto||[]);
  };
"""
new = """  window.journeyBreakdownForSession = function(sess,elapsedSec,kmTotal,fallbackAuto){
    if(!sess?.id) return computeStatusBreakdown(elapsedSec,kmTotal,fallbackAuto||[]);
    ensureJourneyStatus(sess);
    const c=journeyStatusCache.get(journeyKey(sess));
    if(c&&c.rows&&c.rows.length) return statusBreakdownRows(c.rows,elapsedSec,kmTotal,null,null,(S?.gps?.st==='running'?S.gps.sessionId:null));
    if(!c || c.loading) return {total:0,online:{sec:0,km:0,pct:0},buscando:{sec:0,km:0,pct:0},corrida:{sec:0,km:0,pct:0}};
    return computeStatusBreakdown(elapsedSec,kmTotal,fallbackAuto||[]);
  };
"""
assert old in v3, 'V3 session breakdown not found'
v3 = v3.replace(old, new, 1)

# 6) Durante loading, mantém o último DOM válido; não apaga/recria.
old = """  function renderContinuousStatusBars(){
    if(!S?.curDate)return;ensureCivilStatus(S.curDate);
    const c=civilStatusCache.get(S.curDate), rows=c?.rows||[];
    if(rows.length){
      const b=civilDayBounds(S.curDate), bd=statusBreakdownRows(rows,0,0,b.startMs,b.endMs,(S?.gps?.st==='running'?S.gps.sessionId:null));
      const row=document.getElementById('td-bd-row');if(row)row.style.display='';
      try{setHTML('td-bd-bar',buildSbarHtml(bd));setHTML('td-bd-list',buildSrowsHtml(bd));}catch(e){}
    }
    if(S?.gps?.st==='running'&&S.gps.sessionId){
      const sess={id:S.gps.sessionId,start:S.gps.start,end:null,km:S.gps.km||0,elapsed:getElapsed()};
      ensureJourneyStatus(sess);const c2=journeyStatusCache.get(journeyKey(sess));
      if(c2?.rows?.length){const bd=journeyBreakdownForSession(sess,getElapsed(),S.gps.km||0,[]);try{setHTML('jc-bar',buildSbarHtml(bd));setHTML('jc-blist',buildSrowsHtml(bd));}catch(e){}}
    }
  }
"""
new = """  function renderContinuousStatusBars(){
    if(!S?.curDate)return;
    ensureCivilStatus(S.curDate);
    const c=civilStatusCache.get(S.curDate), rows=c?.rows||[];
    const tdRow=document.getElementById('td-bd-row');
    if(rows.length){
      const b=civilDayBounds(S.curDate), bd=statusBreakdownRows(rows,0,0,b.startMs,b.endMs,(S?.gps?.st==='running'?S.gps.sessionId:null));
      if(tdRow)tdRow.style.display='';
      try{setHTML('td-bd-bar',buildSbarHtml(bd));setHTML('td-bd-list',buildSrowsHtml(bd));}catch(e){}
    } else if(c && !c.loading && tdRow) {
      tdRow.style.display='none';
    }

    const jcRow=document.getElementById('jc-breakdown');
    if(S?.gps?.st==='running'&&S.gps.sessionId){
      const sess={id:S.gps.sessionId,start:S.gps.start,end:null,km:S.gps.km||0,elapsed:getElapsed()};
      ensureJourneyStatus(sess);
      const c2=journeyStatusCache.get(journeyKey(sess));
      if(c2?.rows?.length){
        const bd=journeyBreakdownForSession(sess,getElapsed(),S.gps.km||0,[]);
        if(jcRow)jcRow.style.display='';
        try{setHTML('jc-bar',buildSbarHtml(bd));setHTML('jc-blist',buildSrowsHtml(bd));}catch(e){}
      } else if(c2 && !c2.loading && jcRow) {
        jcRow.style.display='none';
      }
    } else if(jcRow) {
      jcRow.style.display='none';
    }
  }
"""
assert old in v3, 'V3 continuous bars not found'
v3 = v3.replace(old, new, 1)

# 7) 1s atualiza só a barra; render completo continua apenas quando necessário.
old = """  setTimeout(()=>{try{if(S.sec==='jornada')renderJornada();}catch(e){}},600);
"""
new = """  setInterval(()=>{try{if(S.sec==='jornada')renderContinuousStatusBars();}catch(e){}},1000);
  setTimeout(()=>{try{if(S.sec==='jornada')renderJornada();}catch(e){}},600);
"""
assert old in v3, 'V3 final timeout not found'
v3 = v3.replace(old, new, 1)

s = head + v3
p.write_text(s, encoding='utf-8')

# Structural validation.
out = p.read_text(encoding='utf-8')
assert 'setInterval(renderStatusTimeline,1000);' not in out
assert 'const autoTripsReady = S._autoTripsDataDate === d;' in out
assert "setInterval(()=>{try{if(S.sec==='jornada')renderContinuousStatusBars();}catch(e){}},1000);" in out
print('Flicker patch OK')
