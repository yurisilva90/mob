from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')

# 1) heartbeat: 5 min -> 30s
old="if (_gpsCloudTick % 300 === 0) _persistGpsCloud().catch(()=>{}); // a cada 5 min"
new="if (_gpsCloudTick % 30 === 0) _persistGpsCloud().catch(()=>{}); // a cada 30s: checkpoint resiliente"
assert old in s, 'gps heartbeat pattern not found'
s=s.replace(old,new,1)

# 2) Resume must not convert background time to paused time.
old_block="""        // Trata o intervalo em que o app ficou sem rastrear (entre o último
        // elapsed salvo e agora) como se fosse uma pausa automática — preserva
        // o horário real de início na tela, mas NÃO conta esse gap como tempo
        // online de verdade (senão o 'Tempo total' fica inflado com tempo em
        // que o app estava fechado, não rodando de fato).
        const expectedNowMs = s.start_ms + (s.elapsed_secs||0)*1000 + (s.paused_ms||0);
        const gapMs = Math.max(0, Date.now() - expectedNowMs);
        g2.pausedMs = (s.paused_ms||0) + gapMs;
"""
new_block="""        // O serviço Android continua rastreando a jornada em background.
        // Portanto, NUNCA transforma o tempo fora da WebView em pausa automática:
        // isso fazia uma jornada de 1h reaparecer com segundos/minutos ao reabrir.
        // Só respeita pausas explicitamente persistidas (o fluxo atual nem usa pausa).
        g2.pausedMs = s.paused_ms || 0;
        // Usa o maior km conhecido entre a sessão e os segmentos nativos da mesma jornada.
        try {
          const { data: segs } = await _SUPA.from('journey_status_segments')
            .select('last_km,end_km,start_km,last_seen_ms')
            .eq('session_id', s.id).order('last_seen_ms',{ascending:false}).limit(20);
          const segKm = (segs||[]).reduce((m,x)=>Math.max(m,parseFloat(x.last_km)||0,parseFloat(x.end_km)||0,parseFloat(x.start_km)||0),0);
          if (segKm > g2.km) g2.km = segKm;
        } catch(e) {}
"""
assert old_block in s, 'resume gap block not found'
s=s.replace(old_block,new_block,1)

# 3) Cloud recovery even if localStorage was lost/reset. Inject immediately before gpsStart.
marker="function gpsStart() {"
assert marker in s, 'gpsStart marker not found'
recovery=r'''
// Recuperação resiliente da jornada: a nuvem é fonte de continuidade quando a
// WebView/localStorage perde o estado, mas o serviço Android continuou ativo.
let _journeyCloudRecoverBusy = false;
async function recoverOpenJourneyFromCloud() {
  if (_journeyCloudRecoverBusy || !_supaUser || !navigator.onLine) return false;
  if (S.gps.st === 'running' || S.gps.st === 'paused') return false;
  _journeyCloudRecoverBusy = true;
  try {
    const cutoff = Date.now() - 16*3600*1000;
    const { data: rows } = await _SUPA.from('sessions').select('*')
      .eq('user_id',_supaUser.id).is('end_ms',null)
      .gte('start_ms',cutoff).order('start_ms',{ascending:false}).limit(1);
    if (!rows || !rows.length) return false;
    const ss = rows[0];
    const g = S.gps;
    let bestKm = parseFloat(ss.km)||0;
    try {
      const { data: segs } = await _SUPA.from('journey_status_segments')
        .select('last_km,end_km,start_km,last_seen_ms')
        .eq('session_id',ss.id).order('last_seen_ms',{ascending:false}).limit(40);
      bestKm = (segs||[]).reduce((m,x)=>Math.max(m,parseFloat(x.last_km)||0,parseFloat(x.end_km)||0,parseFloat(x.start_km)||0),bestKm);
    } catch(e) {}
    if (window.SmartMobiNative) {
      try {
        const nk = SmartMobiNative.getGpsKm?.();
        if (typeof nk === 'number' && isFinite(nk)) bestKm = Math.max(bestKm,nk);
      } catch(e) {}
    }
    g.st='running'; g.sessionId=ss.id; g.start=Number(ss.start_ms);
    g.km=bestKm; g.pausedMs=Number(ss.paused_ms)||0; g.pa=null;
    g.pts=[]; g.lastFixTime=null; g.forceDate=ss.date||null;
    const d=DB.day(ss.date||DB.today());
    g.baseKm=(d.sessions||[]).reduce((a,x)=>a+(x.km||0),0);
    g.baseElapsed=(d.sessions||[]).reduce((a,x)=>a+(x.elapsed||0),0);
    persistGps();
    if (g.ti) clearInterval(g.ti);
    if (g.wid) { try{navigator.geolocation.clearWatch(g.wid)}catch(e){} }
    g.ti=setInterval(gpsUpdate,1000);
    if (navigator.geolocation) g.wid=navigator.geolocation.watchPosition(gpsOnPosition,null,{enableHighAccuracy:true,maximumAge:3000,timeout:10000});
    try {
      if (window.SmartMobiNative && DB.cfg().overlayEnabled !== false) {
        SmartMobiNative.startFloating?.(g.start,g.km||0);
        SmartMobiNative.updateFloatingStatus?.('running');
      }
    } catch(e) {}
    syncNavButton(); requestWakeLock();
    try{renderJornada()}catch(e){} try{renderHome()}catch(e){}
    // Corrige imediatamente o snapshot defasado da sessão na nuvem.
    _persistGpsCloud().catch(()=>{});
    console.warn('[recoverOpenJourneyFromCloud] jornada aberta recuperada',ss.id,'km',bestKm);
    return true;
  } catch(e) {
    console.warn('[recoverOpenJourneyFromCloud]',e);
    return false;
  } finally { _journeyCloudRecoverBusy=false; }
}
// Tenta após autenticação/carregamento e também quando o app volta ao foreground.
setTimeout(()=>recoverOpenJourneyFromCloud().catch(()=>{}),2200);
document.addEventListener('visibilitychange',()=>{
  if (!document.hidden) setTimeout(()=>recoverOpenJourneyFromCloud().catch(()=>{}),350);
});
window.addEventListener('focus',()=>setTimeout(()=>recoverOpenJourneyFromCloud().catch(()=>{}),350));

'''
s=s.replace(marker,recovery+marker,1)

# 4) Persist local snapshot more frequently too: call persistGps on 30s tick.
old="if (_gpsCloudTick % 30 === 0) _persistGpsCloud().catch(()=>{}); // a cada 30s: checkpoint resiliente"
new="if (_gpsCloudTick % 30 === 0) { persistGps(); _persistGpsCloud().catch(()=>{}); } // a cada 30s: local + nuvem"
s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')
print('journey resilience patch applied')
