from pathlib import Path

p=Path('index.html')
s=p.read_text(encoding='utf-8')

old="""  const cachedAutoTrips = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : null;
  if (cachedAutoTrips) {
    S.autoTrips = cachedAutoTrips;
    S._autoTripsDataDate = d;
  }
"""
new="""  const currentAutoTrips = (S._autoTripsDataDate === d && Array.isArray(S.autoTrips)) ? S.autoTrips : [];
  if (!Array.isArray(S._autoTripsByDate[d]) && currentAutoTrips.length > 0) {
    // Se a tela já abriu com dados válidos, eles viram imediatamente o último
    // conjunto conhecido do dia. Assim uma consulta vazia/transitória não zera KPIs.
    S._autoTripsByDate[d] = currentAutoTrips;
  }
  const cachedAutoTrips = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : null;
  if (cachedAutoTrips) {
    S.autoTrips = cachedAutoTrips;
    S._autoTripsDataDate = d;
  }
"""
if old not in s:
    raise SystemExit('Bloco de inicialização do cache não encontrado')
s=s.replace(old,new,1)

old2="""      const prev = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : [];
      // Uma leitura vazia transitória nunca apaga corridas que já foram vistas.
      const stable = (list.length === 0 && prev.length > 0) ? prev : list;
      S._autoTripsByDate[d] = stable;
      S._autoTripsLastFetch[d] = Date.now();
      if (S.curDate === d) {
        S.autoTrips = stable;
        S.autoTripsDate = d;
        S._autoTripsDataDate = d;
        renderJornada();
      }
"""
new2="""      const prev = Array.isArray(S._autoTripsByDate[d])
        ? S._autoTripsByDate[d]
        : ((S._autoTripsDataDate === d && Array.isArray(S.autoTrips)) ? S.autoTrips : []);
      // Uma leitura vazia transitória nunca apaga corridas que já foram vistas.
      const stable = (list.length === 0 && prev.length > 0) ? prev : list;
      S._autoTripsByDate[d] = stable;
      S._autoTripsLastFetch[d] = Date.now();
      if (S.curDate === d) {
        const fingerprint = rows => JSON.stringify((rows || []).map(t => [
          t.id || '', t.offer_value ?? null, t.real_km_trip ?? null,
          t.real_km_pickup ?? null, t.status || '', t.trip_ended_at || ''
        ]));
        const changed = fingerprint(stable) !== fingerprint(S.autoTrips || []);
        S.autoTrips = stable;
        S.autoTripsDate = d;
        S._autoTripsDataDate = d;
        // Evita redesenhar a tela a cada consulta idêntica. Isso elimina a piscada.
        if (changed) renderJornada();
      }
"""
if old2 not in s:
    raise SystemExit('Callback de atualização de auto_trips não encontrado')
s=s.replace(old2,new2,1)

p.write_text(s,encoding='utf-8')

sw=Path('sw.js')
ws=sw.read_text(encoding='utf-8')
if "mob-v26-live-auto-kpi-refresh" in ws:
    ws=ws.replace("mob-v26-live-auto-kpi-refresh","mob-v27-stable-journey-kpis",1)
elif "mob-v27-stable-journey-kpis" not in ws:
    raise SystemExit('Versão esperada do cache não encontrada')
sw.write_text(ws,encoding='utf-8')
print('Journey no-flicker patch applied')
