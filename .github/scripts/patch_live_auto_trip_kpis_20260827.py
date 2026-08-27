from pathlib import Path
import re

index = Path('index.html')
s = index.read_text(encoding='utf-8')

start_marker = "  S._autoTripsByDate = S._autoTripsByDate || {};"
end_marker = "  day.autoTrips = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : (S.autoTrips || []);"
a = s.find(start_marker)
b = s.find(end_marker, a)
if a < 0 or b < 0:
    raise SystemExit('Bloco atual de cache de auto_trips não encontrado; abortando sem alterar.')
b += len(end_marker)

new_block = """  S._autoTripsByDate = S._autoTripsByDate || {};
  S._autoTripsLastFetch = S._autoTripsLastFetch || {};
  S._autoTripsLoading = S._autoTripsLoading || {};

  // A captura automática grava em auto_trips fora do estado JS da tela. Por isso
  // o consolidado precisa reler o dia enquanto a Jornada está visível. Antes,
  // um cache já criado para a data podia permanecer válido no detalhe e antigo
  // no card \"Total do dia\" até alguma outra ação invalidá-lo.
  const cachedAutoTrips = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : null;
  if (cachedAutoTrips) {
    S.autoTrips = cachedAutoTrips;
    S._autoTripsDataDate = d;
  }

  const autoTripsAge = Date.now() - (S._autoTripsLastFetch[d] || 0);
  const autoTripsStale = autoTripsAge >= 15000;
  const autoTripsVisible = typeof document === 'undefined' || document.visibilityState !== 'hidden';
  const shouldRefreshAutoTrips = autoTripsVisible && (S.autoTripsDate !== d || autoTripsStale);

  if (shouldRefreshAutoTrips && !S._autoTripsLoading[d]) {
    S.autoTripsDate = d;
    S._autoTripsLoading[d] = true;
    loadAutoTripsForDay(d).then(list => {
      if (!Array.isArray(list)) return;
      const prev = Array.isArray(S._autoTripsByDate[d]) ? S._autoTripsByDate[d] : [];
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
    }).catch(e => {
      console.warn('[Jornada] refresh auto_trips:', e);
    }).finally(() => {
      S._autoTripsLoading[d] = false;
      // Em falha, evita martelar o banco a cada tick; tenta novamente no próximo TTL.
      if (!S._autoTripsLastFetch[d]) S._autoTripsLastFetch[d] = Date.now();
    });
  }

  day.autoTrips = Array.isArray(S._autoTripsByDate[d])
    ? S._autoTripsByDate[d]
    : ((S._autoTripsDataDate === d && Array.isArray(S.autoTrips)) ? S.autoTrips : []);"""

s = s[:a] + new_block + s[b:]

old_guard = "const canPublishTripKpis = autoTripsReady || legacyTripsHoje.length > 0;"
new_guard = "const canPublishTripKpis = autoTripsReady || autoTripsHoje.length > 0 || legacyTripsHoje.length > 0;"
if old_guard not in s:
    raise SystemExit('Guard dos KPIs não encontrado; abortando sem alterar.')
s = s.replace(old_guard, new_guard, 1)

# Validações estruturais antes de gravar.
assert s.count('const autoTripsAge = Date.now()') == 1
assert new_guard in s

index.write_text(s, encoding='utf-8')

sw = Path('sw.js')
sw_text = sw.read_text(encoding='utf-8')
old_cache = "const CACHE_NAME = 'mob-v25-sw-update-check';"
new_cache = "const CACHE_NAME = 'mob-v26-live-auto-kpi-refresh';"
if old_cache in sw_text:
    sw_text = sw_text.replace(old_cache, new_cache, 1)
elif new_cache not in sw_text:
    raise SystemExit('Versão esperada do service worker não encontrada.')
sw.write_text(sw_text, encoding='utf-8')

print('Patch de atualização ao vivo dos KPIs aplicado.')