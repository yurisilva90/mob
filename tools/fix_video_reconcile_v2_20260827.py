from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')
orig=s

old_resolve="""function resolveTimeConflicts(list) {
      const byTime = new Map();
      list.forEach((t) => {
        const tm = normalizeTime(t.time);
        if(!tm) return;
        t.time = tm;
        const cur = byTime.get(tm);
        if(!cur) { byTime.set(tm, t); return; }
        const curScore = rideCompletenessScore(cur) + (cur._enriched ? 3 : 0);
        const newScore = rideCompletenessScore(t) + (t._enriched ? 3 : 0);
        if(newScore > curScore) {
          mergeFields(t, cur);
          byTime.set(tm, t);
        } else {
          mergeFields(cur, t);
        }
      });
      return [...byTime.values()].sort((a,b)=>timeToMinutes(b.time)-timeToMinutes(a.time));
    }"""
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
        } else {
          out.push({...raw, time: tm, value});
        }
      }
      return out.sort((a,b)=>timeToMinutes(b.time)-timeToMinutes(a.time));
    }"""
if old_resolve in s:
    s=s.replace(old_resolve,new_resolve,1)
elif new_resolve not in s:
    raise SystemExit('resolveTimeConflicts block not found')

old_detail="""const candidate = unique.find(t => normalizeTime(t.time) === dt && !t._enriched);
          if(candidate) { mergeFields(candidate, d); candidate._enriched = true; }"""
new_detail="""const sameTimeCandidates = unique.filter(t => normalizeTime(t.time) === dt && !t._enriched);
          const dv = round2(Number(d.value || d.fare || 0));
          const dPay = String(d.payment_method || d.payment || '').trim().toLowerCase();
          const dCat = String(d.category || d.service || '').trim().toLowerCase();
          const ranked = sameTimeCandidates.map((t) => {
            let score = 0;
            const tv = round2(Number(t.value || 0));
            const tPay = String(t.payment_method || t.payment || '').trim().toLowerCase();
            const tCat = String(t.category || t.service || '').trim().toLowerCase();
            if(dv > 0) score += Math.abs(tv - dv) < 0.01 ? 100 : -50;
            if(dPay && tPay) score += dPay === tPay ? 25 : -10;
            if(dCat && tCat) score += dCat === tCat ? 15 : -5;
            return {t, score};
          }).sort((a,b)=>b.score-a.score);
          let candidate = null;
          if(ranked.length === 1) candidate = ranked[0].t;
          else if(ranked.length > 1 && ranked[0].score > 0 && ranked[0].score > ranked[1].score) candidate = ranked[0].t;
          if(candidate) { mergeFields(candidate, d); candidate._enriched = true; }"""
if old_detail in s:
    s=s.replace(old_detail,new_detail,1)
elif 'const sameTimeCandidates = unique.filter' not in s:
    raise SystemExit('detail enrichment block not found')

old_score="""let score = diff;
            if(fare > 0 && trip.value > 0) score += Math.min(20, Math.abs(fare - trip.value) * 1.5);
            if(isIncomplete) score -= 2;"""
new_score="""let score = diff * 10;
            if(fare > 0 && trip.value > 0) {
              const fareDiff = Math.abs(fare - trip.value);
              if(fareDiff < 0.01) score -= 120;
              else score += Math.min(300, fareDiff * 20);
            }
            if(isIncomplete) score -= 20;"""
if old_score in s:
    s=s.replace(old_score,new_score,1)
elif 'const fareDiff = Math.abs(fare - trip.value);' not in s:
    raise SystemExit('auto trip matching score block not found')

if 'RECONCILIAÇÃO OBRIGATÓRIA DO VÍDEO' not in s:
    anchors=[
        'Não repita a mesma corrida em frames diferentes.',
        'Não duplique a mesma corrida em frames diferentes.',
    ]
    instruction=" RECONCILIAÇÃO OBRIGATÓRIA DO VÍDEO: trate o vídeo como sequência temporal de uma lista rolável, não como imagens independentes. Reconstrua os cards e mescle leituras parciais do mesmo card. HH:mm NÃO é identificador único: duas corridas podem ocorrer no mesmo minuto; mantenha ambas quando valor, pagamento, categoria ou rota diferirem. Ordene pelo horário textual, nunca pela ordem dos frames. Nunca copie horário de card vizinho. 'Outro', ajustes, taxas, créditos/débitos e valores negativos NÃO são corridas. Normalize valores e endereços, preserve App/Dinheiro e faça reconciliação global antes da resposta."
    for anchor in anchors:
        if anchor in s:
            s=s.replace(anchor,anchor+instruction,1)
            break

if s != orig:
    p.write_text(s,encoding='utf-8')
    print('video reconciliation v2 applied')
else:
    print('video reconciliation v2 already applied')
