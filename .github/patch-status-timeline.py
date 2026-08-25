from pathlib import Path
import re

p = Path('index.html')
s = p.read_text(encoding='utf-8')

# 1) Corrige a janela do dia para o fuso LOCAL do aparelho e distingue erro de lista vazia.
old = '''async function loadAutoTripsForDay(dateStr) {\n  if (!_supaUser) return [];\n  const from = dateStr+'T00:00:00', to = dateStr+'T23:59:59';\n  const { data, error } = await _SUPA.from('auto_trips').select('*')\n    .eq('user_id', _supaUser.id)\n    .is('data_quality_flag', null)\n    .gte('trip_started_at', from).lte('trip_started_at', to)\n    .order('trip_started_at', {ascending:true});\n  return error ? [] : (data||[]);\n}'''
new = '''async function loadAutoTripsForDay(dateStr) {\n  if (!_supaUser) return [];\n  // O dia da Jornada é o dia LOCAL do motorista. Converte meia-noite local\n  // para UTC antes de consultar timestamptz — evita perder corridas após 21h\n  // no Brasil quando o relógio UTC já virou para o dia seguinte.\n  const fromLocal = new Date(dateStr+'T00:00:00');\n  const toLocal = new Date(fromLocal); toLocal.setDate(toLocal.getDate()+1);\n  const { data, error } = await _SUPA.from('auto_trips').select('*')\n    .eq('user_id', _supaUser.id)\n    .is('data_quality_flag', null)\n    .gte('trip_started_at', fromLocal.toISOString()).lt('trip_started_at', toLocal.toISOString())\n    .order('trip_started_at', {ascending:true});\n  // null = falha de rede/consulta; [] = consulta válida sem corridas.\n  return error ? null : (data||[]);\n}'''
assert old in s
s = s.replace(old, new, 1)

# 2) Não apaga o último cache válido enquanto atualiza.
old = '''  if (S.autoTripsDate !== d) {\n    S.autoTripsDate = d;\n    S.autoTrips = [];\n    loadAutoTripsForDay(d).then(list => {\n      if (S.autoTripsDate !== d) return; // usuário já trocou de dia\n      S.autoTrips = list;\n      renderJornada();\n    });\n  }'''
new = '''  if (S.autoTripsDate !== d) {\n    const keepCurrent = S._autoTripsDataDate === d ? (S.autoTrips || []) : [];\n    S.autoTripsDate = d;\n    S.autoTrips = keepCurrent;\n    loadAutoTripsForDay(d).then(list => {\n      if (S.autoTripsDate !== d || !Array.isArray(list)) return; // erro mantém último dado válido\n      S.autoTrips = list;\n      S._autoTripsDataDate = d;\n      renderJornada();\n    });\n  }'''
assert old in s
s = s.replace(old, new, 1)

old = '''async function _refreshAutoTripsIfOnJornada() {\n  if (!(S && S.sec === 'jornada' && S.curDate)) return;\n  try {\n    const list = await loadAutoTripsForDay(S.curDate);\n    S.autoTrips = list; S.autoTripsDate = S.curDate;\n    renderJornada();\n  } catch(e) {}\n}'''
new = '''async function _refreshAutoTripsIfOnJornada() {\n  if (!(S && S.sec === 'jornada' && S.curDate)) return;\n  try {\n    const list = await loadAutoTripsForDay(S.curDate);\n    if (!Array.isArray(list)) return; // falha não vira "zero corridas"\n    S.autoTrips = list; S.autoTripsDate = S.curDate; S._autoTripsDataDate = S.curDate;\n    renderJornada();\n  } catch(e) {}\n}'''
assert old in s
s = s.replace(old, new, 1)

# 3) Substitui o patch realtime anterior por timeline independente de auto_trips.
pat = re.compile(r'<!-- JOURNEY_REALTIME_SESSION_V1 -->.*?</script>', re.S)
assert pat.search(s)
replacement = r'''<!-- JOURNEY_STATUS_TIMELINE_V2 -->
<script>
(function(){
  let statusSegmentsDate = null;
  let statusSegments = [];
  let statusLoading = false;
  let nativeSessionBound = null;

  function nativeStatusTimeline(){
    try{
      if(window.SmartMobiNative && typeof SmartMobiNative.getJourneyStatusTimeline === 'function'){
        const raw = SmartMobiNative.getJourneyStatusTimeline();
        if(!raw) return [];
        const v = typeof raw === 'string' ? JSON.parse(raw) : raw;
        return Array.isArray(v) ? v : [];
      }
    }catch(e){}
    return [];
  }

  function ensureNativeJourneySession(){
    try{
      if(!window.SmartMobiNative || typeof SmartMobiNative.setJourneySession !== 'function') return;
      if(!S || !S.gps || S.gps.st !== 'running' || !S.gps.sessionId || !S.gps.start) return;
      if(nativeSessionBound === S.gps.sessionId) return;
      // Sessão criada há poucos segundos = nova. Uma sessão antiga retomada\n      // após kill/reinstalação NÃO ganha passado inventado como Online.
      const isNew = Math.abs(Date.now() - Number(S.gps.start)) < 15000;
      SmartMobiNative.setJourneySession(S.gps.sessionId, DB.today(), Number(S.gps.start), Number(S.gps.km)||0, isNew);
      nativeSessionBound = S.gps.sessionId;
    }catch(e){}
  }

  async function loadStatusSegments(dateStr){
    if(!_supaUser || statusLoading) return;
    statusLoading = true;
    try{
      const {data,error} = await _SUPA.from('journey_status_segments').select('*')
        .eq('user_id', _supaUser.id).eq('date', dateStr).order('start_ms',{ascending:true});
      if(!error){ statusSegments = data||[]; statusSegmentsDate = dateStr; }
    }catch(e){} finally { statusLoading = false; }
  }

  function segmentEndMs(seg, isLiveSession){
    if(seg.end_ms != null) return Number(seg.end_ms)||Number(seg.start_ms)||0;
    if(isLiveSession) return Date.now();
    return Number(seg.last_seen_ms)||Number(seg.start_ms)||0;
  }
  function segmentEndKm(seg, isLiveSession){
    if(seg.end_km != null) return Number(seg.end_km)||0;
    if(isLiveSession && S && S.gps) return Number(S.gps.km)||0;
    return Number(seg.last_km)||Number(seg.start_km)||0;
  }

  function breakdownFromSegments(elapsedSec, kmTotal, segments, liveSessionId){
    const out = {
      total: Math.max(0,Number(elapsedSec)||0),
      online:{sec:0,km:0,pct:0}, buscando:{sec:0,km:0,pct:0}, corrida:{sec:0,km:0,pct:0}
    };
    (segments||[]).forEach(seg=>{
      const status = seg.status === 'buscar' ? 'buscando' : seg.status;
      if(!out[status]) return;
      const start = Number(seg.start_ms)||0;
      const live = !!liveSessionId && seg.session_id === liveSessionId && seg.end_ms == null;
      const end = segmentEndMs(seg, live);
      const sec = Math.max(0,(end-start)/1000);
      const skm = Number(seg.start_km)||0;
      const ekm = segmentEndKm(seg, live);
      out[status].sec += sec;
      out[status].km += Math.max(0,ekm-skm);
    });
    // Tempo/km que ainda não tem trecho explícito continua como Online, mas\n    // NUNCA apaga os trechos Buscar/Corrida já registrados.
    const trackedSec = out.online.sec+out.buscando.sec+out.corrida.sec;
    const trackedKm = out.online.km+out.buscando.km+out.corrida.km;
    out.online.sec += Math.max(0,out.total-trackedSec);
    out.online.km += Math.max(0,(Number(kmTotal)||0)-trackedKm);
    const pct = v => out.total>0 ? Math.round(Math.max(0,v)/out.total*100) : 0;
    out.online.pct=pct(out.online.sec); out.buscando.pct=pct(out.buscando.sec); out.corrida.pct=pct(out.corrida.sec);
    return out;
  }

  function manualTripTs(t,dateStr){
    if(!t) return 0;
    let ts=Number(t.ts)||0;
    if(!ts&&t.created_at) ts=Date.parse(t.created_at)||0;
    if(!ts&&t.accepted_at) ts=Date.parse(t.accepted_at)||0;
    if(!ts&&t.trip_started_at) ts=Date.parse(t.trip_started_at)||0;
    if(!ts&&t.time&&dateStr) ts=new Date(dateStr+'T'+t.time+':00').getTime();
    return ts||0;
  }

  function currentSessionTrips(day,startMs){
    const dateStr=day&&day.date?day.date:DB.today();
    const manual=(day&&day.trips?day.trips:[]).filter(t=>manualTripTs(t,dateStr)>=startMs);
    const auto=(day&&day.autoTrips?day.autoTrips:[]).filter(t=>{
      try{ const ts=typeof autoTripTs==='function'?autoTripTs(t):Date.parse(t.trip_started_at||t.accepted_at||'')||0; return ts&&ts>=startMs; }
      catch(e){return false;}
    });
    return {manual,auto};
  }

  function mergedTodaySegments(){
    const live = (S && S.gps && S.gps.st==='running') ? nativeStatusTimeline() : [];
    const sid = S&&S.gps ? S.gps.sessionId : null;
    const cloud = (statusSegmentsDate===S.curDate ? statusSegments : []).filter(x=>!sid || x.session_id!==sid);
    return cloud.concat(live);
  }

  function renderStatusTimeline(){
    try{
      if(!S||!DB||S.sec!=='jornada') return;
      ensureNativeJourneySession();
      if(S.curDate && statusSegmentsDate!==S.curDate) loadStatusSegments(S.curDate);

      const day=DB.day(S.curDate||DB.today());
      const isToday=S.curDate===DB.today();
      const live=isToday&&S.gps&&S.gps.st==='running'&&S.gps.start;

      // Card verde: somente a Jornada atual.
      if(live){
        const elapsed=Math.max(0,typeof getElapsed==='function'?getElapsed():0);
        const km=Math.max(0,Number(S.gps.km)||0);
        const trips=currentSessionTrips(day,Number(S.gps.start)||0);
        const ganhos=trips.manual.reduce((a,t)=>a+(Number(t.value)||0),0)+trips.auto.reduce((a,t)=>a+(Number(t.offer_value)||0),0);
        if(typeof setText==='function'){
          setText('jc-trips2',trips.manual.length+trips.auto.length);
          setText('jc-rsh2',elapsed>0?DB.fRI(ganhos/(elapsed/3600)):'R$0,00');
          setText('jc-rskm2',km>0?DB.fRI(ganhos/km):'R$0,00');
        }
        const native=nativeStatusTimeline();
        const bd=breakdownFromSegments(elapsed,km,native,S.gps.sessionId);
        const jc=document.getElementById('jc-breakdown');
        if(jc){ jc.style.display=''; setHTML('jc-bar',buildSbarHtml(bd)); setHTML('jc-blist',buildSrowsHtml(bd)); }
      }

      // Total do dia: soma trechos persistidos de TODAS as jornadas + trecho vivo.
      const finished=(day.sessions||[]);
      const totalElapsed=finished.reduce((a,x)=>a+(x.elapsed||0),0)+(live?getElapsed():0)+(day.tempoAdjust||0);
      const totalKm=finished.reduce((a,x)=>a+(x.km||0),0)+(live?(Number(S.gps.km)||0):0)+(day.kmAdjust||0);
      const td=document.getElementById('td-bd-row');
      if(td&&totalElapsed>0){
        const bd=breakdownFromSegments(totalElapsed,totalKm,mergedTodaySegments(),live?S.gps.sessionId:null);
        td.style.display=''; setHTML('td-bd-bar',buildSbarHtml(bd)); setHTML('td-bd-list',buildSrowsHtml(bd));
      }
    }catch(e){ console.warn('[JourneyStatusTimeline]',e); }
  }
  window.renderStatusTimeline=renderStatusTimeline;

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
})();
</script>'''
s = pat.sub(replacement, s, count=1)

p.write_text(s, encoding='utf-8')
print('Patch timeline da Jornada aplicado.')
