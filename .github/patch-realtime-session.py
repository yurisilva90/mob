from pathlib import Path

path = Path('index.html')
html = path.read_text(encoding='utf-8')
marker = '<!-- JOURNEY_REALTIME_SESSION_V1 -->'
if marker in html:
    raise SystemExit('Patch já existe no index.html')

injection = r'''
<!-- JOURNEY_REALTIME_SESSION_V1 -->
<script>
(function(){
  // Estado vivo vem do APK 1.3.5+. Em versões antigas retorna null e a
  // Jornada continua funcionando com os dados consolidados já existentes.
  function mobNativeLiveTripState(){
    try{
      if(window.SmartMobiNative && typeof SmartMobiNative.getLiveTripState === 'function'){
        const raw = SmartMobiNative.getLiveTripState();
        if(!raw) return null;
        return typeof raw === 'string' ? JSON.parse(raw) : raw;
      }
    }catch(e){}
    return null;
  }

  function mobManualTripTs(t, dateStr){
    if(!t) return 0;
    let ts = Number(t.ts)||0;
    if(!ts && t.created_at) ts = Date.parse(t.created_at)||0;
    if(!ts && t.accepted_at) ts = Date.parse(t.accepted_at)||0;
    if(!ts && t.trip_started_at) ts = Date.parse(t.trip_started_at)||0;
    if(!ts && t.time && dateStr) ts = new Date(dateStr+'T'+t.time+':00').getTime();
    return ts||0;
  }

  function mobCurrentSessionAutoTrips(day, startMs){
    return (day && day.autoTrips ? day.autoTrips : []).filter(t => {
      try{
        const ts = typeof autoTripTs === 'function' ? autoTripTs(t) :
          Date.parse(t.trip_started_at || t.accepted_at || '') || 0;
        return ts && ts >= startMs;
      }catch(e){ return false; }
    });
  }

  function mobCurrentSessionManualTrips(day, startMs){
    const dateStr = day && day.date ? day.date : (typeof DB !== 'undefined' ? DB.today() : '');
    return (day && day.trips ? day.trips : []).filter(t => mobManualTripTs(t, dateStr) >= startMs);
  }

  // Mesma estrutura consumida por buildSbarHtml/buildSrowsHtml, porém soma
  // ao histórico já encerrado o trecho que ESTÁ acontecendo agora no APK.
  function mobComputeLiveBreakdown(elapsedSec, kmTotal, autoTrips, liveState){
    let corridaSec = 0, buscandoSec = 0, corridaKm = 0, buscandoKm = 0;

    (autoTrips || []).forEach(t => {
      if(t.trip_started_at && t.trip_ended_at){
        const s = (new Date(t.trip_ended_at) - new Date(t.trip_started_at))/1000;
        if(s > 0) corridaSec += s;
        corridaKm += parseFloat(t.real_km_trip ?? t.offer_km_trip) || 0;
      }
      if(t.pickup_started_at && t.trip_started_at){
        const s = (new Date(t.trip_started_at) - new Date(t.pickup_started_at))/1000;
        if(s > 0) buscandoSec += s;
        buscandoKm += parseFloat(t.real_km_pickup ?? t.offer_km_pickup) || 0;
      }
    });

    if(liveState && liveState.active){
      const nowMs = Date.now();
      const pickupStartedAt = Number(liveState.pickupStartedAt)||0;
      const tripStartedAt = Number(liveState.tripStartedAt)||0;
      const pickupStartKm = Number(liveState.pickupStartKm)||0;
      const tripStartKm = Number(liveState.tripStartKm)||0;
      const currentKm = Number.isFinite(Number(liveState.gpsKm)) ? Number(liveState.gpsKm) : Number(kmTotal)||0;

      if(pickupStartedAt > 0 && tripStartedAt > 0){
        buscandoSec += Math.max(0, (tripStartedAt-pickupStartedAt)/1000);
        buscandoKm += Math.max(0, tripStartKm-pickupStartKm);
        corridaSec += Math.max(0, (nowMs-tripStartedAt)/1000);
        corridaKm += Math.max(0, currentKm-tripStartKm);
      }else if(pickupStartedAt > 0){
        buscandoSec += Math.max(0, (nowMs-pickupStartedAt)/1000);
        buscandoKm += Math.max(0, currentKm-pickupStartKm);
      }
    }

    const total = Math.max(0, Number(elapsedSec)||0);
    const onlineSec = Math.max(0, total-corridaSec-buscandoSec);
    const onlineKm = Math.max(0, (Number(kmTotal)||0)-corridaKm-buscandoKm);
    const pct = s => total > 0 ? Math.round(Math.max(0,s)/total*100) : 0;
    return {
      total,
      online:   {sec:onlineSec,   km:onlineKm,   pct:pct(onlineSec)},
      buscando: {sec:buscandoSec, km:buscandoKm, pct:pct(buscandoSec)},
      corrida:  {sec:corridaSec,  km:corridaKm,  pct:pct(corridaSec)}
    };
  }

  function mobRenderCurrentSessionRealtime(){
    try{
      if(typeof S === 'undefined' || typeof DB === 'undefined' || !S.gps) return;
      if(S.curDate !== DB.today() || S.gps.st !== 'running' || !S.gps.start) return;

      const day = DB.day(DB.today());
      const startMs = Number(S.gps.start)||0;
      const elapsed = typeof getElapsed === 'function' ? Math.max(0,getElapsed()) : 0;
      const km = Math.max(0, Number(S.gps.km)||0);
      const manualTrips = mobCurrentSessionManualTrips(day, startMs);
      const autoTrips = mobCurrentSessionAutoTrips(day, startMs);
      const ganhos = manualTrips.reduce((s,t)=>s+(Number(t.value)||0),0)
                   + autoTrips.reduce((s,t)=>s+(Number(t.offer_value)||0),0);
      const corridas = manualTrips.length + autoTrips.length;

      // SOMENTE o card verde da sessão atual. O Total do dia usa ids sem o
      // sufixo "2" e permanece intocado/consolidado.
      if(typeof setText === 'function'){
        setText('jc-trips2', corridas);
        const rsh = elapsed > 0 ? ganhos/(elapsed/3600) : null;
        const rskm = km > 0 ? ganhos/km : null;
        setText('jc-rsh2', rsh !== null ? DB.fRI(rsh) : 'R$0,00');
        setText('jc-rskm2', rskm !== null ? DB.fRI(rskm) : 'R$0,00');

        // Mantém a mesma régua visual dos indicadores, mas calculada com a
        // sessão atual em vez do consolidado do dia.
        const rateEl = document.getElementById('jc-rate-hora2');
        const kmEl = document.getElementById('jc-rate-km2');
        const rateCls = rsh !== null && typeof rateColorClass === 'function' ? rateColorClass('rhora', rsh) : '';
        const kmCls = rskm !== null && typeof rateColorClass === 'function' ? rateColorClass('rkm', rskm) : '';
        if(rateEl) rateEl.className = 'rate-cell '+rateCls;
        if(kmEl) kmEl.className = 'rate-cell '+kmCls;
      }

      // Barra da jornada atual: segundos, km e percentuais atualizados a
      // cada tick, inclusive ANTES de a corrida terminar e ir ao Supabase.
      const jcBd = document.getElementById('jc-breakdown');
      if(jcBd && elapsed > 0){
        jcBd.style.display = '';
        const liveState = mobNativeLiveTripState();
        const bd = mobComputeLiveBreakdown(elapsed, km, autoTrips, liveState);
        if(typeof setHTML === 'function' && typeof buildSbarHtml === 'function' && typeof buildSrowsHtml === 'function'){
          setHTML('jc-bar', buildSbarHtml(bd));
          setHTML('jc-blist', buildSrowsHtml(bd));
        }
      }
    }catch(e){
      console.warn('[Jornada realtime]', e);
    }
  }
  window.mobRenderCurrentSessionRealtime = mobRenderCurrentSessionRealtime;

  // Corrige imediatamente depois de qualquer render completo da Jornada.
  if(typeof window.renderJornada === 'function'){
    const originalRenderJornada = window.renderJornada;
    window.renderJornada = function(){
      const r = originalRenderJornada.apply(this, arguments);
      setTimeout(mobRenderCurrentSessionRealtime, 0);
      return r;
    };
  }

  // gpsUpdate já roda a cada 1s durante a jornada. O intervalo adicional é
  // uma rede de segurança para WebViews onde a referência antiga do timer
  // tenha sido criada antes deste wrapper.
  if(typeof window.gpsUpdate === 'function'){
    const originalGpsUpdate = window.gpsUpdate;
    window.gpsUpdate = function(){
      const r = originalGpsUpdate.apply(this, arguments);
      mobRenderCurrentSessionRealtime();
      return r;
    };
  }
  setInterval(mobRenderCurrentSessionRealtime, 1000);
  setTimeout(mobRenderCurrentSessionRealtime, 500);
})();
</script>
'''

if '</body>' not in html:
    raise SystemExit('Não encontrei </body> no index.html')
head, tail = html.rsplit('</body>', 1)
path.write_text(head + injection + '\n</body>' + tail, encoding='utf-8')
print('Patch realtime da sessão atual aplicado.')
