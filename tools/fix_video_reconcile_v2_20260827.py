from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')
orig=s

def function_end(text, start):
    brace=text.find('{',start)
    if brace < 0: return -1
    depth=0; quote=None; esc=False; i=brace
    while i < len(text):
        ch=text[i]
        if quote:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch==quote: quote=None
        else:
            if ch in ('\"', "'", '`'): quote=ch
            elif ch=='{': depth+=1
            elif ch=='}':
                depth-=1
                if depth==0: return i+1
        i+=1
    return -1

new_resolve="""function resolveTimeConflicts(list) {
      const out = [];
      for(const raw of (list || [])) {
        const tm = normalizeTime(raw && raw.time);
        const value = round2(Number(raw && raw.value) || 0);
        if(!tm || value <= 0) continue;
        const pay = String(raw && (raw.payment_method || raw.payment) || '').trim().toLowerCase();
        const cat = String(raw && (raw.category || raw.service) || '').trim().toLowerCase();
        const duplicate = out.find((x) => {
          if(normalizeTime(x.time) !== tm) return false;
          if(Math.abs((Number(x.value) || 0) - value) >= 0.01) return false;
          const xPay = String(x.payment_method || x.payment || '').trim().toLowerCase();
          const xCat = String(x.category || x.service || '').trim().toLowerCase();
          if(pay && xPay && pay !== xPay) return false;
          if(cat && xCat && cat !== xCat) return false;
          return true;
        });
        if(duplicate) {
          mergeFields(duplicate, raw);
          duplicate._enriched = !!(duplicate._enriched || raw._enriched);
        } else out.push({...raw, time: tm, value});
      }
      return out.sort((a,b)=>timeToMinutes(b.time)-timeToMinutes(a.time));
    }"""
start=s.find('function resolveTimeConflicts(list)'); end=function_end(s,start) if start>=0 else -1
if start<0 or end<0: raise SystemExit('resolver not found')
if 'const out = [];' not in s[start:end] or 'value <= 0' not in s[start:end]: s=s[:start]+new_resolve+s[end:]

old_details="""details.forEach(d => {
    let cand = null;
    if (d.time) cand = unique.find(u => u.time === d.time && !u._enriched);
    if (!cand && (d.originFull || d.destFull)) {
      cand = unique.find(u => !u._enriched &&
        ((d.originFull && u.originFull === d.originFull) || (d.destFull && u.destFull === d.destFull)));
    }
    if (cand) {
      cand._enriched = true;
      if (d.km != null && d.km > 0)       { cand.km = d.km; cand.kmEstimado = false; }
      if (d.duration != null && d.duration > 0) cand.duration = d.duration;
      // Endereço do detalhe é a linha inteira, sem truncar — prefere ele.
      if (d.originFull) { cand.originFull = d.originFull; cand.origin = d.origin; }
      if (d.destFull)   { cand.destFull = d.destFull; cand.dest = d.dest; }
    }
  });"""
new_details="""details.forEach(d => {
    let cand = null;
    const dTime = normalizeTime(d.time);
    const sameTimeCandidates = dTime ? unique.filter(u => normalizeTime(u.time) === dTime && !u._enriched) : [];
    if (sameTimeCandidates.length === 1) cand = sameTimeCandidates[0];
    else if (sameTimeCandidates.length > 1) {
      const dValue = round2(Number(d.value || d.fare || 0));
      const dOrigin = _normRoute(d.originFull || d.origin || '');
      const dDest = _normRoute(d.destFull || d.dest || '');
      const ranked = sameTimeCandidates.map(u => {
        let score = 0;
        if(dValue > 0) score += Math.abs(round2(Number(u.value||0))-dValue) < 0.01 ? 100 : -50;
        const uOrigin = _normRoute(u.originFull || u.origin || '');
        const uDest = _normRoute(u.destFull || u.dest || '');
        if(dOrigin && uOrigin) score += (uOrigin.includes(dOrigin)||dOrigin.includes(uOrigin)) ? 35 : -10;
        if(dDest && uDest) score += (uDest.includes(dDest)||dDest.includes(uDest)) ? 35 : -10;
        return {u,score};
      }).sort((a,b)=>b.score-a.score);
      if(ranked[0] && ranked[0].score > 0 && (!ranked[1] || ranked[0].score > ranked[1].score)) cand = ranked[0].u;
    }
    if (!cand && (d.originFull || d.destFull)) {
      const dOrigin = _normRoute(d.originFull || d.origin || '');
      const dDest = _normRoute(d.destFull || d.dest || '');
      cand = unique.find(u => !u._enriched &&
        ((dOrigin && _normRoute(u.originFull || u.origin || '').includes(dOrigin)) ||
         (dDest && _normRoute(u.destFull || u.dest || '').includes(dDest))));
    }
    if (cand) {
      cand._enriched = true;
      if (d.km != null && d.km > 0) { cand.km = d.km; cand.kmEstimado = false; }
      if (d.duration != null && d.duration > 0) cand.duration = d.duration;
      if (d.originFull) { cand.originFull = d.originFull; cand.origin = d.origin; }
      if (d.destFull) { cand.destFull = d.destFull; cand.dest = d.dest; }
    }
  });"""
if old_details in s: s=s.replace(old_details,new_details,1)
elif 'const sameTimeCandidates = dTime ? unique.filter' not in s: raise SystemExit('details block not found')

new_match="""function matchAutoTrip(newT, autoTrips) {
  let best = null, bestScore = -Infinity;
  for (const at of (autoTrips || [])) {
    if ((at.platform||'uber') !== (newT.platform||'uber')) continue;
    const atTime = _autoTripLocalTime(at);
    if (!atTime || !newT.time) continue;
    const [h1,m1] = atTime.split(':').map(Number), [h2,m2] = newT.time.split(':').map(Number);
    const diff = Math.abs((h1*60+m1)-(h2*60+m2));
    if (diff > 12) continue;
    const fare = Number(at.offer_value||0), value = Number(newT.value||0);
    const fareDiff = Math.abs(fare-value);
    const sameVal = fare > 0 && value > 0 && fareDiff < 0.02;
    const sameKm = Number(newT.km)>0 && Number(at.real_km_trip)>0 && Math.abs(Number(at.real_km_trip)-Number(newT.km)) < 0.5;
    const sameRoute = !!(at.origin_address && newT.origin && at.dest_address && newT.dest &&
      _normRoute(at.origin_address).includes(_normRoute(newT.origin)) && _normRoute(at.dest_address).includes(_normRoute(newT.dest)));
    const incomplete = at.capture_complete === false || fare <= 0 || at.value_needs_review === true;
    if (!sameVal && !sameKm && !sameRoute && !incomplete) continue;
    let score = diff === 0 ? 45 : (diff <= 5 ? 32 : 14);
    if (sameVal) score += 120;
    else if (fare > 0 && value > 0) score -= Math.min(100, fareDiff * 8);
    if (sameKm) score += 55;
    if (sameRoute) score += 55;
    if (incomplete) score += 20;
    if (incomplete && diff <= 5) score += 20;
    if (score > bestScore) { bestScore = score; best = at; }
  }
  return bestScore >= 45 ? best : null;
}"""
start=s.find('function matchAutoTrip(newT, autoTrips)'); end=function_end(s,start) if start>=0 else -1
if start<0 or end<0: raise SystemExit('matchAutoTrip not found')
if 'bestScore >= 45' not in s[start:end]: s=s[:start]+new_match+s[end:]

if 'RECONCILIAÇÃO OBRIGATÓRIA DO VÍDEO' not in s:
    for anchor in ['Não repita a mesma corrida em frames diferentes.','Não duplique a mesma corrida em frames diferentes.']:
        if anchor in s:
            s=s.replace(anchor,anchor+" RECONCILIAÇÃO OBRIGATÓRIA DO VÍDEO: trate o vídeo como sequência temporal de uma lista rolável, não como imagens independentes. Reconstrua os cards e mescle leituras parciais do mesmo card. HH:mm NÃO é identificador único: duas corridas podem ocorrer no mesmo minuto; mantenha ambas quando valor, pagamento, categoria ou rota diferirem. Ordene pelo horário textual, nunca pela ordem dos frames. Nunca copie horário de card vizinho. 'Outro', ajustes, taxas, créditos/débitos e valores negativos NÃO são corridas. Normalize valores e endereços, preserve App/Dinheiro e faça reconciliação global antes da resposta.",1); break

if s != orig:
    p.write_text(s,encoding='utf-8'); print('video reconciliation v2 applied')
else: print('video reconciliation v2 already applied')
# final-functional-trigger
