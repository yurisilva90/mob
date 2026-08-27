from pathlib import Path
import re

p = Path('index.html')
s = p.read_text(encoding='utf-8')
orig = s

# 1) Never collapse distinct rides just because they share the same HH:mm.
# Exact duplicates are already removed by absorb() using time+value.
pat = r"    function resolveTimeConflicts\(list\) \{.*?\n    \}\n\n    function applyDetails"
rep = '''    function resolveTimeConflicts(list) {
      // v2: HH:mm is NOT a unique ride id. 99 can have two legitimate rides
      // at the same minute (e.g. 10:11 with different values/payment modes).
      // Only collapse records that are effectively the same observation.
      const out = [];
      for (const raw of (list || [])) {
        const t = normalizeTime(raw && raw.time);
        const v = round2(Number(raw && raw.value) || 0);
        if (!t || v <= 0) continue;
        const pay = String(raw && (raw.payment_method || raw.payment) || '').toLowerCase();
        const cat = String(raw && (raw.category || raw.service) || '').toLowerCase();
        const dup = out.find(x => normalizeTime(x.time) === t && Math.abs((Number(x.value)||0)-v) < 0.01 &&
          (!pay || !String(x.payment_method||x.payment||'').toLowerCase() || String(x.payment_method||x.payment||'').toLowerCase() === pay) &&
          (!cat || !String(x.category||x.service||'').toLowerCase() || String(x.category||x.service||'').toLowerCase() === cat));
        if (dup) {
          mergeFields(dup, raw);
          dup._enriched = !!(dup._enriched || raw._enriched);
        } else out.push({ ...raw, time: t, value: v });
      }
      // History is displayed newest first; normalize deterministically by textual HH:mm.
      return out.sort((a,b) => timeToMinutes(b.time) - timeToMinutes(a.time));
    }

    function applyDetails'''
s, n1 = re.subn(pat, rep, s, count=1, flags=re.S)
if n1 != 1:
    raise SystemExit(f'resolveTimeConflicts patch failed: {n1}')

# 2) Strengthen AI extraction contract: card identity, scrolling, same-time rides,
# financial rows, field preservation, and global reconciliation before output.
needle = "Não repita a mesma corrida em frames diferentes."
extra = """Não repita a mesma corrida em frames diferentes. RECONCILIAÇÃO OBRIGATÓRIA DO VÍDEO: trate o vídeo como uma sequência temporal de uma lista rolável, não como imagens independentes. Reconstrua primeiro os CARDS visíveis e acompanhe o mesmo card entre frames pela combinação de posição/movimento do scroll + horário + valor + pagamento + categoria + origem/destino. Um card pode aparecer parcial em um frame e completo no seguinte: nesses casos MESCLAR os campos e preservar sempre a leitura mais completa/confiável; nunca criar duas corridas. IMPORTANTE: horário HH:mm NÃO é identificador único — podem existir duas corridas legítimas no mesmo minuto; se o horário for igual mas valor, pagamento, categoria ou rota forem diferentes, mantenha ambas. Nunca atribua a uma corrida o horário de um card vizinho só porque o horário dela não está visível. Ordene o resultado final pelo horário textual exibido no histórico, e não pela ordem dos frames. Antes de responder faça uma reconciliação global de todas as observações do vídeo. Linhas financeiras/ajustes que não sejam corrida (por exemplo categoria 'Outro', crédito/débito/ajuste/taxa, especialmente valor negativo como -R$) NÃO são corridas e devem ser descartadas. Normalize R$/vírgula/ponto, abreviações e pequenas variações de endereço antes de comparar. Uma corrida final deve ter value > 0 e evidência de card de corrida. Se houver duas leituras conflitantes do mesmo campo, escolha a leitura mais completa e com maior evidência visual. Para pagamento, preserve explicitamente app ou dinheiro quando aparecer. Só devolva corridas consolidadas após essa segunda passagem global."""
if needle not in s:
    raise SystemExit('AI prompt needle not found')
s = s.replace(needle, extra, 1)

# 3) Make detail-fragment matching score-based instead of consuming the first same-time
# candidate. This prevents two rides at 10:11 from stealing each other's route/payment.
old = "const candidate = unique.find(t => normalizeTime(t.time) === dt && !t._enriched);"
new = """const sameTimeCandidates = unique.filter(t => normalizeTime(t.time) === dt && !t._enriched);
          const dv = round2(Number(d.value || d.fare || 0));
          const dpay = String(d.payment_method || d.payment || '').toLowerCase();
          const dcat = String(d.category || d.service || '').toLowerCase();
          const candidate = sameTimeCandidates
            .map(t => {
              let score = 0;
              const tv = round2(Number(t.value || 0));
              if (dv > 0 && Math.abs(tv - dv) < 0.01) score += 100;
              else if (dv > 0) score -= 50;
              const tpay = String(t.payment_method || t.payment || '').toLowerCase();
              const tcat = String(t.category || t.service || '').toLowerCase();
              if (dpay && tpay && dpay === tpay) score += 25;
              if (dcat && tcat && dcat === tcat) score += 15;
              return { t, score };
            })
            .sort((a,b) => b.score - a.score)[0]?.t || null;"""
if old not in s:
    raise SystemExit('detail candidate needle not found')
s = s.replace(old, new, 1)

# 4) Do not let a weaker later fragment overwrite a good populated field.
# mergeFields already fills missing fields only; keep that behavior explicit in comment/version.
s = s.replace("const VIDEO_IMPORT_VERSION =", "const VIDEO_RECONCILE_V2 = '2026-08-27';\n  const VIDEO_IMPORT_VERSION =", 1) if "const VIDEO_IMPORT_VERSION =" in s else s

if s == orig:
    raise SystemExit('no changes')
p.write_text(s, encoding='utf-8')
print('video reconcile v2 applied')
