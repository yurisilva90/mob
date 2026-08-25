from pathlib import Path

p=Path('index.html')
s=p.read_text(encoding='utf-8')

def one(old,new,label):
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: esperado 1, encontrado {n}')
    return s.replace(old,new,1)

# Tag de origem separada do status de confirmação.
s=one(
    '.chip-auto{background:#EFF6FF;color:#0EA5E9}.auto-status{',
    '.chip-auto{background:#EFF6FF;color:#0EA5E9}.chip-import{background:#F5F3FF;color:#7C3AED}.auto-status{',
    'css tag importada'
)
s=one(
    '  const extras = [`<span class="chip chip-auto">Captura automática</span>`];',
    '  const sourceTag = t.capture_source === \'importada\' ? `<span class="chip chip-import">Importada</span>` : `<span class="chip chip-auto">Captura automática</span>`;\n  const extras = [sourceTag];',
    'tag origem autoTripItem'
)

# Status visível agora é binário: aguardando confirmação ou confirmada.
s=one(
    "  const statusCls = t.value_needs_review ? 'susp' : (t.status==='confirmada' ? 'conf' : (t.status==='estimada' ? 'estim' : 'pend'));\n  const statusTxt = t.value_needs_review ? 'Valor a confirmar' : (t.status==='confirmada' ? 'Confirmada' : (t.status==='estimada' ? 'Aguardando confirmação' : 'Aguardando revisão'));",
    "  const statusCls = t.status==='confirmada' ? 'conf' : 'estim';\n  const statusTxt = t.status==='confirmada' ? 'Confirmada' : 'Aguardando confirmação';",
    'status visual binario'
)

# Banner laranja continua sendo a entrada principal para o vídeo. Qualquer
# corrida não confirmada (ou ainda marcada tecnicamente para revisão) conta.
s=one(
    "      const pendingCount = autoTripsHoje.filter(t => t.status === 'capturada' || t.status === 'estimada').length;",
    "      const pendingCount = autoTripsHoje.filter(t => t.status !== 'confirmada' || t.value_needs_review === true).length;",
    'contagem banner pendente'
)

# Corrida nova encontrada no vídeo: já nasce Confirmada; a origem fica na tag.
s=one(
    "      status: 'importada',\n      import_video_id: videoId",
    "      status: 'confirmada',\n      capture_source: 'importada',\n      value_needs_review: false,\n      data_quality_flag: null,\n      import_video_id: videoId",
    'nova importada confirmada'
)

# Corrida automática casada pelo vídeo mantém capture_source=automatica e
# somente muda o estado de confirmação/qualidade.
s=one(
    "      status: 'confirmada',\n      import_video_id: videoId || undefined",
    "      status: 'confirmada',\n      value_needs_review: false,\n      data_quality_flag: null,\n      import_video_id: videoId || undefined",
    'confirmacao automatica pelo video'
)

# Comentário coerente com a nova semântica (não funcional, evita confusão futura).
s=s.replace(
    "    // Nova — nunca vista na captura ao vivo. Vira auto_trips com status\n    // 'importada' (pedido do Yuri, 16/08/2026) — unifica com o resto dos",
    "    // Nova — nunca vista na captura ao vivo. Vira auto_trips já Confirmada\n    // pelo vídeo; 'Importada' agora é somente a tag de origem — unifica com o resto dos",
    1
)

# Sanidades.
required=[
    "t.capture_source === 'importada'",
    "statusTxt = t.status==='confirmada' ? 'Confirmada' : 'Aguardando confirmação'",
    "pendingCount = autoTripsHoje.filter(t => t.status !== 'confirmada' || t.value_needs_review === true).length",
    "capture_source: 'importada'",
    "value_needs_review: false",
]
for x in required:
    if x not in s: raise SystemExit(f'faltou validar: {x}')

p.write_text(s,encoding='utf-8')
