from pathlib import Path
import re

p = Path('index.html')
s = p.read_text(encoding='utf-8')

# 1) Jornada passa a pertencer ao dia em que COMEÇOU, nunca ao dia do encerramento.
old = "  const closeDate = g.forceDate || DB.today();"
assert old in s, 'closeDate antigo não encontrado'
s = s.replace(old, "  const closeDate = _ymd(startMs); // Jornada contínua: identidade fica no dia em que começou", 1)

old = "    date:       g.forceDate || DB.today(),"
assert old in s, 'data do checkpoint antigo não encontrada'
s = s.replace(old, "    date:       _ymd(g.start), // Jornada contínua: não troca de identidade à meia-noite", 1)

# 2) O card de uma Jornada usa a timeline persistente quando disponível.
old = "  const sessBd = computeStatusBreakdown(elapsedSecs, km, autoTrips);"
assert old in s, 'sessBd antigo não encontrado'
s = s.replace(old, "  const sessBd = (typeof journeyBreakdownForSession === 'function')\n    ? journeyBreakdownForSession(sess, elapsedSecs, km, autoTrips)\n    : computeStatusBreakdown(elapsedSecs, km, autoTrips);", 1)

# 3) Vídeo de conferência ganha plataforma + data/período operacional.
old = "async function uploadImportVideo(file) {"
assert old in s
s = s.replace(old, "async function uploadImportVideo(file, plat, operationalDate) {", 1)

old = "    const path = `${_supaUser.id}/${DB.uid()}.${ext}`;"
assert old in s
s = s.replace(old, "    const opDate = operationalDate || S.curDate || DB.today();\n    const opPlat = normalizeOperationalPlatform(plat);\n    const opRange = operationalRangeForPlatform(opPlat, opDate);\n    const path = `${_supaUser.id}/${opDate}/${opPlat}/${DB.uid()}.${ext}`;", 1)

old = "      user_id: _supaUser.id, storage_path: path, file_size_bytes: file.size || null"
assert old in s
s = s.replace(old, "      user_id: _supaUser.id, storage_path: path, file_size_bytes: file.size || null,\n      platform: opPlat, operational_date: opDate,\n      period_start: new Date(opRange.startMs).toISOString(),\n      period_end: new Date(opRange.endMs).toISOString()", 1)

old = "async function processImportBatch(images, videos, plat) {\n  const targetCount ="
assert old in s
s = s.replace(old, "async function processImportBatch(images, videos, plat) {\n  const operationalDate = S.curDate || DB.today();\n  const operationalPlat = normalizeOperationalPlatform(plat);\n  window._pendingImportOperationalDate = operationalDate;\n  window._pendingImportPlatform = operationalPlat;\n  const targetCount =", 1)

old = "    videoUploads.push(uploadImportVideo(videos[v]));"
assert old in s
s = s.replace(old, "    videoUploads.push(uploadImportVideo(videos[v], operationalPlat, operationalDate));", 1)

old = "  const autoTripsPool = (S.autoTripsDate === S.curDate) ? (S.autoTrips||[]).slice() : await loadAutoTripsForDay(S.curDate);"
assert old in s
s = s.replace(old, "  const autoTripsPool = (await loadAutoTripsForOperationalDay(operationalPlat, operationalDate)) || [];", 1)

old = "    try { startMs = new Date(S.curDate + 'T' + (t.time||'00:00') + ':00').getTime(); } catch(e) { startMs = NaN; }"
assert old in s
s = s.replace(old, "    try {\n      const opDate = window._pendingImportOperationalDate || S.curDate || DB.today();\n      startMs = operationalTimestampForTime(t.platform || window._pendingImportPlatform, opDate, t.time||'00:00');\n    } catch(e) { startMs = NaN; }", 1)

# 4) Na tela Corridas, quando UMA plataforma está selecionada, agrupa pelo dia operacional dela.
#    Sem filtro ou com Uber+99 juntos, mantém o dia civil (não existe um corte único para as duas).
start = s.index('async function renderCorridasActive()')
end = s.index('function autoCorridasDateRange()', start)
block = s[start:end]
old = "      const d = new Date(ts);\n      const dateStr = d.getFullYear()+'-'+p2(d.getMonth()+1)+'-'+p2(d.getDate());"
assert old in block, 'agrupamento Corridas não encontrado'
new = "      const d = new Date(ts);\n      const onePlat = plats.size === 1 ? [...plats][0] : null;\n      const dateStr = onePlat ? operationalDateForTimestamp(onePlat, ts) : localYmdFromMs(ts);"
block = block.replace(old, new, 1)
s = s[:start] + block + s[end:]

# Ofertas recusadas seguem o mesmo agrupamento operacional quando uma plataforma é filtrada.
start = s.index('async function renderDeclinedOffers(')
end = s.index('\n}', start) + 2
# Não precisamos achar o fim perfeito para a substituição: limitamos a uma janela ampla da função.
window = s[start:start+12000]
old = "    const d = new Date(o.seen_at);\n    const dateStr = d.getFullYear()+'-'+p2(d.getMonth()+1)+'-'+p2(d.getDate());"
assert old in window, 'agrupamento recusadas não encontrado'
new = "    const d = new Date(o.seen_at);\n    const onePlat = plats.size === 1 ? [...plats][0] : null;\n    const dateStr = onePlat ? operationalDateForTimestamp(onePlat, d.getTime()) : localYmdFromMs(d.getTime());"
window = window.replace(old, new, 1)
s = s[:start] + window + s[start+12000:]

# 5) Camada V3: jornada contínua + dias operacionais + listagem virtual por dia.
addon = r'''

<!-- JOURNEY_CONTINUOUS_OPERATIONAL_V3 -->
<script>
(function(){
  // ── Datas e dias operacionais ───────────────────────────────────────
  window.localYmdFromMs = function(ms){
    const d = new Date(Number(ms)||Date.now());
    return d.getFullYear()+'-'+p2(d.getMonth()+1)+'-'+p2(d.getDate());
  };
  window.normalizeOperationalPlatform = function(p){
    return String(p||'uber').toLowerCase() === '99' ? '99' : 'uber';
  };
  window.civilDayBounds = function(dateStr){
    const start = new Date(dateStr+'T00:00:00');
    const end = new Date(start); end.setDate(end.getDate()+1);
    return {startMs:start.getTime(), endMs:end.getTime()};
  };
  window.operationalRangeForPlatform = function(plat,dateStr){
    const p = normalizeOperationalPlatform(plat);
    const start = new Date(dateStr+'T00:00:00');
    if(p === 'uber') start.setHours(4,0,0,0);
    const end = new Date(start); end.setDate(end.getDate()+1);
    return {platform:p, operationalDate:dateStr, startMs:start.getTime(), endMs:end.getTime()};
  };
  window.operationalDateForTimestamp = function(plat,ts){
    const p = normalizeOperationalPlatform(plat);
    const d = new Date(Number(ts));
    // Uber: tudo de 00:00 até 03:59 ainda pertence ao dia operacional anterior.
    if(p === 'uber' && d.getHours() < 4) d.setDate(d.getDate()-1);
    return localYmdFromMs(d.getTime());
  };
  window.operationalTimestampForTime = function(plat,dateStr,hhmm){
    const p = normalizeOperationalPlatform(plat);
    const parts = String(hhmm||'00:00').split(':').map(Number);
    const h = Number.isFinite(parts[0]) ? parts[0] : 0;
    const m = Number.isFinite(parts[1]) ? parts[1] : 0;
    const d = new Date(dateStr+'T00:00:00');
    d.setHours(h,m,0,0);
    if(p === 'uber' && h < 4) d.setDate(d.getDate()+1);
    return d.getTime();
  };
  window.loadAutoTripsForOperationalDay = async function(plat,dateStr){
    if(!_supaUser) return [];
    const r = operationalRangeForPlatform(plat,dateStr);
    let q = _SUPA.from('auto_trips').select('*')
      .eq('user_id',_supaUser.id)
      .is('data_quality_flag',null)
      .eq('platform',normalizeOperationalPlatform(plat))
      .gte('trip_started_at',new Date(r.startMs).toISOString())
      .lt('trip_started_at',new Date(r.endMs).toISOString())
      .order('trip_started_at',{ascending:true});
    const {data,error} = await q;
    return error ? [] : (data||[]);
  };

  // ── Filtro da tela Corridas ────────────────────────────────────────
  const _civilGetCorridasDays = window.getCorridasDays;
  window.getCorridasDays = function(){
    const plats = S.corridasPlats || new Set();
    const onePlat = plats.size === 1 ? [...plats][0] : null;
    if(!onePlat) return _civilGetCorridasDays();
    const anchorStr = operationalDateForTimestamp(onePlat,Date.now());
    const anchor = new Date(anchorStr+'T12:00:00');
    const fmt = d => localYmdFromMs(d.getTime());
    const p = S.corridasPeriod;
    if(p==='date' && S.corridasDate) return [S.corridasDate];
    if(p==='hoje') return [anchorStr];
    if(p==='7d') { const out=[]; for(let i=0;i<7;i++){const d=new Date(anchor);d.setDate(d.getDate()-i);out.push(fmt(d));} return out; }
    if(p==='mes') {
      const y=anchor.getFullYear(), m=anchor.getMonth();
      const dim=new Date(y,m+1,0).getDate(), out=[];
      for(let day=1;day<=dim;day++) out.push(y+'-'+p2(m+1)+'-'+p2(day));
      return out;
    }
    return _civilGetCorridasDays();
  };
  window.autoCorridasDateRange = function(){
    const dates = getCorridasDays().slice().sort();
    if(!dates.length) return null;
    const plats = S.corridasPlats || new Set();
    const onePlat = plats.size===1 ? [...plats][0] : null;
    if(onePlat){
      const a=operationalRangeForPlatform(onePlat,dates[0]);
      const b=operationalRangeForPlatform(onePlat,dates[dates.length-1]);
      return {from:new Date(a.startMs).toISOString(),to:new Date(b.endMs-1).toISOString()};
    }
    const a=civilDayBounds(dates[0]), b=civilDayBounds(dates[dates.length-1]);
    return {from:new Date(a.startMs).toISOString(),to:new Date(b.endMs-1).toISOString()};
  };

  // ── Jornada contínua: nunca mais pergunta/divide à meia-noite ─────
  window.checkMidnightCrossing = function(){ return; };
  window.openMidnightModal = function(){ S._midnightModalOpen=false; try{closeMo('mo-midnight');}catch(e){} };
  window.resolveMidnightSplit = async function(){ S._midnightModalOpen=false; try{closeMo('mo-midnight');}catch(e){} };
  window.splitJourneyAtMidnight = async function(){ return; };
  window.openPostStopMidnightModal = function(sess,onDone){
    S._midnightIsPostStop=false; S._postStopMidnightSess=null; S._postMidnightCallback=null; S._midnightModalOpen=false;
    try{closeMo('mo-midnight');}catch(e){}
    if(typeof onDone==='function') onDone();
  };
  window.resolvePostStopMidnight = async function(){ S._midnightIsPostStop=false; S._midnightModalOpen=false; try{closeMo('mo-midnight');}catch(e){} };
  try { if(S && S.gps) S.gps.forceDate = null; } catch(e) {}

  // ── Corridas de uma Jornada: busca por INTERVALO REAL, não por data ──
  const journeyAutoCache = new Map();
  const journeyStatusCache = new Map();
  const overlapSessionCache = new Map();
  const civilStatusCache = new Map();

  function journeyKey(sess){ return String(sess?.id || ((sess?.start||0)+'_'+(sess?.end||'live'))); }
  function sessionEnd(sess){ return Number(sess?.end || ((S?.gps?.sessionId && sess?.id===S.gps.sessionId) ? Date.now() : Date.now())); }
  function overlaps(start,end,a,b){ return Number(start||0) < b && Number(end||Date.now()) >= a; }

  async function ensureJourneyAutoTrips(sess){
    if(!_supaUser || !sess?.start) return;
    const k=journeyKey(sess), old=journeyAutoCache.get(k);
    const ttl=sess.end?120000:12000;
    if(old && (old.loading || Date.now()-old.ts<ttl)) return;
    journeyAutoCache.set(k,{loading:true,ts:Date.now(),rows:old?.rows||[]});
    try{
      const end=sessionEnd(sess);
      const {data,error}=await _SUPA.from('auto_trips').select('*')
        .eq('user_id',_supaUser.id).is('data_quality_flag',null)
        .gte('trip_started_at',new Date(Number(sess.start)).toISOString())
        .lte('trip_started_at',new Date(end).toISOString())
        .order('trip_started_at',{ascending:true});
      if(!error) journeyAutoCache.set(k,{loading:false,ts:Date.now(),rows:data||[]});
    }catch(e){ journeyAutoCache.set(k,{loading:false,ts:Date.now(),rows:old?.rows||[]}); }
    try{ if(S.sec==='jornada') setTimeout(()=>renderJornada(),0); }catch(e){}
  }
  function journeyAutoTrips(sess,fallback){
    const k=journeyKey(sess), c=journeyAutoCache.get(k);
    ensureJourneyAutoTrips(sess);
    const rows=(c&&Array.isArray(c.rows)&&c.rows.length)?c.rows:(fallback||[]);
    const a=Number(sess?.start||0), b=sessionEnd(sess);
    const seen=new Set();
    return rows.filter(t=>{const ts=autoTripTs(t); if(!ts||ts<a||ts>b)return false; const id=t.id||ts+'_'+t.offer_value; if(seen.has(id))return false; seen.add(id); return true;});
  }
  function journeyManualTrips(sess){
    const a=Number(sess?.start||0), b=sessionEnd(sess), out=[], seen=new Set();
    (DB.allDates?DB.allDates():[]).forEach(ds=>{
      const d=DB.day(ds);
      (d.trips||[]).forEach(t=>{
        let ts=Number(t.ts)||0;
        if(!ts&&t.time) ts=new Date(ds+'T'+t.time+':00').getTime();
        if(!ts||ts<a||ts>b)return;
        const id=t.id||ts+'_'+(t.value||0); if(seen.has(id))return; seen.add(id);
        out.push(Object.assign({},t,{ts,_ts:ts}));
      });
    });
    return out;
  }

  // ── Timeline real Online/Buscar/Corrida por Jornada ────────────────
  async function ensureJourneyStatus(sess){
    if(!_supaUser || !sess?.id) return;
    const k=journeyKey(sess), old=journeyStatusCache.get(k), ttl=sess.end?120000:8000;
    if(old && (old.loading || Date.now()-old.ts<ttl)) return;
    journeyStatusCache.set(k,{loading:true,ts:Date.now(),rows:old?.rows||[]});
    try{
      const {data,error}=await _SUPA.from('journey_status_segments').select('*')
        .eq('user_id',_supaUser.id).eq('session_id',sess.id).order('start_ms',{ascending:true});
      if(!error) journeyStatusCache.set(k,{loading:false,ts:Date.now(),rows:data||[]});
    }catch(e){ journeyStatusCache.set(k,{loading:false,ts:Date.now(),rows:old?.rows||[]}); }
    try{ if(S.sec==='jornada') setTimeout(()=>renderJornada(),0); }catch(e){}
  }
  function statusBreakdownRows(rows,elapsedSec,kmTotal,clipStart,clipEnd,liveSessionId){
    const out={total:Math.max(0,Number(elapsedSec)||0),online:{sec:0,km:0,pct:0},buscando:{sec:0,km:0,pct:0},corrida:{sec:0,km:0,pct:0}};
    (rows||[]).forEach(seg=>{
      const key=seg.status==='buscar'?'buscando':seg.status; if(!out[key])return;
      const rawStart=Number(seg.start_ms)||0;
      const isLive=!!liveSessionId&&seg.session_id===liveSessionId&&seg.end_ms==null;
      const rawEnd=Number(seg.end_ms||(isLive?Date.now():seg.last_seen_ms)||rawStart);
      if(rawEnd<=rawStart)return;
      const a=Math.max(rawStart,clipStart==null?rawStart:clipStart);
      const b=Math.min(rawEnd,clipEnd==null?rawEnd:clipEnd);
      if(b<=a)return;
      const sec=(b-a)/1000;
      let sk=Number(seg.start_km)||0;
      let ek=Number(seg.end_km!=null?seg.end_km:(isLive&&S?.gps?S.gps.km:seg.last_km))||sk;
      const frac=(b-a)/(rawEnd-rawStart);
      const km=Math.max(0,(ek-sk)*frac);
      out[key].sec+=sec; out[key].km+=km;
    });
    const tracked=out.online.sec+out.buscando.sec+out.corrida.sec;
    const trackedKm=out.online.km+out.buscando.km+out.corrida.km;
    if(out.total<=0) out.total=tracked;
    else if(clipStart==null && clipEnd==null){
      out.online.sec+=Math.max(0,out.total-tracked);
      out.online.km+=Math.max(0,(Number(kmTotal)||0)-trackedKm);
    }
    const pct=v=>out.total>0?Math.round(Math.max(0,v)/out.total*100):0;
    out.online.pct=pct(out.online.sec);out.buscando.pct=pct(out.buscando.sec);out.corrida.pct=pct(out.corrida.sec);
    return out;
  }
  window.journeyBreakdownForSession = function(sess,elapsedSec,kmTotal,fallbackAuto){
    if(!sess?.id) return computeStatusBreakdown(elapsedSec,kmTotal,fallbackAuto||[]);
    ensureJourneyStatus(sess);
    const c=journeyStatusCache.get(journeyKey(sess));
    if(c&&c.rows&&c.rows.length) return statusBreakdownRows(c.rows,elapsedSec,kmTotal,null,null,(S?.gps?.st==='running'?S.gps.sessionId:null));
    return computeStatusBreakdown(elapsedSec,kmTotal,fallbackAuto||[]);
  };

  // ── Jornadas que atravessam a data selecionada ────────────────────
  async function ensureOverlapSessions(dateStr){
    if(!_supaUser||!dateStr)return;
    const old=overlapSessionCache.get(dateStr);
    if(old&&(old.loading||Date.now()-old.ts<30000))return;
    overlapSessionCache.set(dateStr,{loading:true,ts:Date.now(),rows:old?.rows||[]});
    const b=civilDayBounds(dateStr);
    try{
      const {data,error}=await _SUPA.from('sessions').select('*').eq('user_id',_supaUser.id)
        .lt('start_ms',b.endMs).or(`end_ms.is.null,end_ms.gte.${b.startMs}`).order('start_ms',{ascending:true});
      if(!error){
        const rows=data||[];
        overlapSessionCache.set(dateStr,{loading:false,ts:Date.now(),rows});
        // Hidratamos o cache local no DIA DE INÍCIO; nunca criamos uma segunda Jornada na virada.
        rows.filter(r=>r.end_ms).forEach(r=>{
          const ds=localYmdFromMs(r.start_ms), day=DB.day(ds); if(!day.sessions)day.sessions=[];
          const item={id:r.id,start:Number(r.start_ms),end:Number(r.end_ms),km:parseFloat(r.km)||0,elapsed:r.elapsed_secs||0};
          const i=day.sessions.findIndex(x=>x.id===item.id); if(i>=0)day.sessions[i]=item; else day.sessions.push(item); DB.saveDay(day);
        });
      }
    }catch(e){overlapSessionCache.set(dateStr,{loading:false,ts:Date.now(),rows:old?.rows||[]});}
    try{if(S.sec==='jornada')setTimeout(()=>renderJornada(),0);}catch(e){}
  }
  function overlappingJourneyDescriptors(dateStr){
    const b=civilDayBounds(dateStr), map=new Map();
    (DB.allDates?DB.allDates():[]).forEach(ds=>{
      const day=DB.day(ds);(day.sessions||[]).forEach((sess,idx)=>{
        if(!overlaps(sess.start,sess.end,b.startMs,b.endMs))return;
        map.set(String(sess.id||sess.start),{sess,sourceDate:ds,origIdx:idx});
      });
    });
    const remote=overlapSessionCache.get(dateStr)?.rows||[];
    remote.forEach(r=>{
      if(!overlaps(r.start_ms,r.end_ms,b.startMs,b.endMs))return;
      const id=String(r.id||r.start_ms);if(map.has(id))return;
      const ds=localYmdFromMs(r.start_ms), d=DB.day(ds), idx=(d.sessions||[]).findIndex(x=>x.id===r.id);
      map.set(id,{sess:{id:r.id,start:Number(r.start_ms),end:r.end_ms?Number(r.end_ms):null,km:parseFloat(r.km)||0,elapsed:r.elapsed_secs||0},sourceDate:ds,origIdx:idx});
    });
    if(S?.gps?.st==='running'&&S.gps.start&&overlaps(S.gps.start,null,b.startMs,b.endMs)){
      const id=String(S.gps.sessionId||S.gps.start);
      map.set(id,{sess:{id:S.gps.sessionId,start:S.gps.start,end:null,km:S.gps.km||0,elapsed:getElapsed()},sourceDate:localYmdFromMs(S.gps.start),origIdx:-1,live:true});
    }
    return [...map.values()].sort((a,b)=>(a.sess.start||0)-(b.sess.start||0));
  }
  function journeyLabel(desc,dateStr){
    const sess=desc.sess, src=desc.sourceDate||localYmdFromMs(sess.start);
    if(desc.live) return src===dateStr?'Jornada atual':'Jornada atual · continuação';
    const srcSessions=(DB.day(src).sessions||[]).slice().sort((a,b)=>(a.start||0)-(b.start||0));
    const pos=Math.max(0,srcSessions.findIndex(x=>x.id===sess.id));
    let label='Jornada '+(pos+1);
    const endDate=sess.end?localYmdFromMs(sess.end):src;
    if(src<dateStr) label+=' · continuação'; else if(endDate>dateStr) label+=' · continua';
    return label;
  }
  function renderContinuousSessionList(){
    const el=document.getElementById('sessions-list'), toggle=document.getElementById('sessions-toggle');
    if(!el||!S?.curDate)return;
    ensureOverlapSessions(S.curDate);
    const desc=overlappingJourneyDescriptors(S.curDate).sort((a,b)=>(b.sess.start||0)-(a.sess.start||0));
    const shown=S.sessionsExpanded?desc:desc.slice(0,3);
    const html=shown.map(x=>{
      ensureJourneyAutoTrips(x.sess);ensureJourneyStatus(x.sess);
      const synthetic={date:x.sourceDate,trips:journeyManualTrips(x.sess),autoTrips:journeyAutoTrips(x.sess,DB.day(x.sourceDate).autoTrips||[])};
      return sessionItem(journeyLabel(x,S.curDate),x.sess,x.origIdx,x.sourceDate,synthetic,!!x.live);
    });
    el.innerHTML=html.length?html.join(''):'<div class="empty">Nenhuma sessão registrada</div>';
    if(toggle){toggle.style.display=desc.length>3?'':'none';toggle.innerHTML=S.sessionsExpanded?'Ver menos':'Ver todas &#8250;';}
  }

  // Link de corrida ↔ Jornada agora procura TODAS as sessões; uma corrida de 01:30
  // pode pertencer à Jornada iniciada no dia anterior.
  window.isAutoTripLinkedToSession = function(t){
    const ts=autoTripTs(t);if(!ts)return false;
    for(const ds of (DB.allDates?DB.allDates():[])){
      if((DB.day(ds).sessions||[]).some(sess=>ts>=(sess.start||0)&&(!sess.end||ts<=sess.end)))return true;
    }
    return !!(S?.gps?.st==='running'&&S.gps.start&&ts>=S.gps.start);
  };

  // ── Barra Total do dia = corte CIVIL virtual da timeline ───────────
  async function ensureCivilStatus(dateStr){
    if(!_supaUser||!dateStr)return;
    const old=civilStatusCache.get(dateStr);if(old&&(old.loading||Date.now()-old.ts<8000))return;
    civilStatusCache.set(dateStr,{loading:true,ts:Date.now(),rows:old?.rows||[]});
    const b=civilDayBounds(dateStr);
    try{
      const {data,error}=await _SUPA.from('journey_status_segments').select('*').eq('user_id',_supaUser.id)
        .lt('start_ms',b.endMs).or(`end_ms.is.null,end_ms.gte.${b.startMs}`).order('start_ms',{ascending:true});
      if(!error)civilStatusCache.set(dateStr,{loading:false,ts:Date.now(),rows:data||[]});
    }catch(e){civilStatusCache.set(dateStr,{loading:false,ts:Date.now(),rows:old?.rows||[]});}
    try{if(S.sec==='jornada')setTimeout(()=>renderJornada(),0);}catch(e){}
  }
  function renderContinuousStatusBars(){
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

  const previousRenderJornada=window.renderJornada;
  window.renderJornada=function(){
    previousRenderJornada();
    try{renderContinuousSessionList();}catch(e){console.warn('[continuous journeys]',e);}
    try{renderContinuousStatusBars();}catch(e){console.warn('[continuous status]',e);}
  };

  setTimeout(()=>{try{if(S.sec==='jornada')renderJornada();}catch(e){}},600);
})();
</script>
'''
assert '</body>' in s
s = s.replace('</body>', addon + '\n</body>', 1)

p.write_text(s, encoding='utf-8')
print('Patch operacional aplicado:', len(s), 'bytes')
