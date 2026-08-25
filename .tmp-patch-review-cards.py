from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')

def rep(old, new, count=1, label=''):
    global s
    n = s.count(old)
    if n != count:
        raise SystemExit('ASSERT %s: esperado %s, encontrado %s' % (label or old[:50], count, n))
    s = s.replace(old, new, count)

# data_quality_flag continua existindo como metadado, mas não exclui corridas
# das consultas que alimentam Jornada, Home, Metas e cards operacionais.
rep("\n    .is('data_quality_flag', null)\n", "\n", 2, 'filtros de cards')
rep("\n      .is('data_quality_flag',null)\n", "\n", 1, 'filtro operacional')
rep(".eq('user_id',_supaUser.id).is('data_quality_flag',null)\n        .gte('trip_started_at'", ".eq('user_id',_supaUser.id)\n        .gte('trip_started_at'", 1, 'filtro por Jornada')

# Não cria um pseudo-status 'Suspeita'. Usa os estados canônicos já existentes.
rep(
    "  const statusCls = t.data_quality_flag ? 'susp' : (t.value_needs_review ? 'susp' : (t.status==='confirmada' ? 'conf' : (t.status==='estimada' ? 'estim' : 'pend')));\n  const statusTxt = t.data_quality_flag ? 'Suspeita — revisar' : (t.value_needs_review ? 'Valor a confirmar' : (t.status==='confirmada' ? 'Confirmada' : (t.status==='estimada' ? 'Aguardando confirmação' : 'Aguardando revisão')));",
    "  const statusCls = t.value_needs_review ? 'susp' : (t.status==='confirmada' ? 'conf' : (t.status==='estimada' ? 'estim' : 'pend'));\n  const statusTxt = t.value_needs_review ? 'Valor a confirmar' : (t.status==='confirmada' ? 'Confirmada' : (t.status==='estimada' ? 'Aguardando confirmação' : 'Aguardando revisão'));",
    1, 'badge canônico'
)

# Home: mesmo recorte local já usado na Jornada, sem perder corridas após 21h.
rep(
    "  const from = fromDate+'T00:00:00', to = toDate+'T23:59:59';\n  const { data, error } = await _SUPA.from('auto_trips').select('*')\n    .eq('user_id', _supaUser.id)\n    .gte('trip_started_at', from).lte('trip_started_at', to)",
    "  const fromLocal = new Date(fromDate+'T00:00:00');\n  const toLocal = new Date(toDate+'T00:00:00'); toLocal.setDate(toLocal.getDate()+1);\n  const { data, error } = await _SUPA.from('auto_trips').select('*')\n    .eq('user_id', _supaUser.id)\n    .gte('trip_started_at', fromLocal.toISOString()).lt('trip_started_at', toLocal.toISOString())",
    1, 'limite local Home'
)

# Se a timeline só cobre parte da Jornada, o restante continua Online.
rep(
    "    if(out.total<=0) out.total=tracked;\n    else if(clipStart==null && clipEnd==null){\n      out.online.sec+=Math.max(0,out.total-tracked);\n      out.online.km+=Math.max(0,(Number(kmTotal)||0)-trackedKm);\n    }",
    "    if(out.total<=0) out.total=tracked;\n    else {\n      out.online.sec+=Math.max(0,out.total-tracked);\n      out.online.km+=Math.max(0,(Number(kmTotal)||0)-trackedKm);\n    }",
    1, 'restante online'
)

marker = "  // ── Barra Total do dia = corte CIVIL virtual da timeline ───────────\n"
helper = """  function civilJourneyTotals(dateStr){
    const b=civilDayBounds(dateStr), seen=new Set();
    let elapsed=0, km=0;
    const add=sess=>{
      const start=Number(sess?.start||0); if(!start)return;
      const live=!!(S?.gps?.st==='running' && S.gps.sessionId && sess?.id===S.gps.sessionId);
      let end=Number(sess?.end||0);
      const recordedElapsed=Math.max(0,Number(sess?.elapsed)||0);
      if(!end) end=live?Date.now():(recordedElapsed>0?start+recordedElapsed*1000:0);
      if(!end||end<=start)return;
      const a=Math.max(start,b.startMs), z=Math.min(end,b.endMs); if(z<=a)return;
      const key=String(sess?.id||start+'_'+end); if(seen.has(key))return; seen.add(key);
      const wall=Math.max(1,end-start), frac=(z-a)/wall;
      const baseElapsed=recordedElapsed>0?recordedElapsed:wall/1000;
      elapsed+=Math.max(0,baseElapsed*frac);
      km+=Math.max(0,Number(sess?.km)||0)*frac;
    };
    try{(DB.allDates?DB.allDates():[]).forEach(ds=>(DB.day(ds).sessions||[]).forEach(add));}catch(e){}
    if(S?.gps?.st==='running'&&S.gps.start){
      add({id:S.gps.sessionId,start:S.gps.start,end:null,elapsed:getElapsed(),km:S.gps.km||0});
    }
    try{
      const day=DB.day(dateStr);
      elapsed=Math.max(0,elapsed+(Number(day.tempoAdjust)||0));
      km=Math.max(0,km+(Number(day.kmAdjust)||0));
    }catch(e){}
    return {elapsed,km};
  }

""" + marker
rep(marker, helper, 1, 'helper total civil')

old = """  function renderContinuousStatusBars(){
    if(!S?.curDate)return;
    ensureCivilStatus(S.curDate);
    const c=civilStatusCache.get(S.curDate), rows=c?.rows||[];
    const tdRow=document.getElementById('td-bd-row');
    if(rows.length){
      const b=civilDayBounds(S.curDate), bd=statusBreakdownRows(rows,0,0,b.startMs,b.endMs,(S?.gps?.st==='running'?S.gps.sessionId:null));
      if(tdRow)tdRow.style.display='';
      try{setHTML('td-bd-bar',buildSbarHtml(bd));setHTML('td-bd-list',buildSrowsHtml(bd));}catch(e){}
    } else if(c && !c.loading && tdRow) {
      tdRow.style.display='none';
    }
"""
new = """  function renderContinuousStatusBars(){
    if(!S?.curDate)return;
    ensureCivilStatus(S.curDate);
    const c=civilStatusCache.get(S.curDate), rows=c?.rows||[];
    const tdRow=document.getElementById('td-bd-row');
    const totals=civilJourneyTotals(S.curDate);
    if(rows.length){
      const b=civilDayBounds(S.curDate), bd=statusBreakdownRows(rows,totals.elapsed,totals.km,b.startMs,b.endMs,(S?.gps?.st==='running'?S.gps.sessionId:null));
      if(tdRow)tdRow.style.display='';
      try{setHTML('td-bd-bar',buildSbarHtml(bd));setHTML('td-bd-list',buildSrowsHtml(bd));}catch(e){}
    } else if(c && !c.loading) {
      const day=DB.day(S.curDate);
      const autos=(day.autoTrips&&day.autoTrips.length)?day.autoTrips:((S._autoTripsDataDate===S.curDate&&Array.isArray(S.autoTrips))?S.autoTrips:[]);
      const bd=computeStatusBreakdown(totals.elapsed,totals.km,autos);
      const hasJourney=totals.elapsed>0||totals.km>0||autos.length>0;
      if(tdRow)tdRow.style.display=hasJourney?'':'none';
      if(hasJourney){try{setHTML('td-bd-bar',buildSbarHtml(bd));setHTML('td-bd-list',buildSrowsHtml(bd));}catch(e){}}
    }
"""
rep(old, new, 1, 'fallback barra total')

if 'Suspeita — revisar' in s:
    raise SystemExit('badge Suspeita ainda presente')
remaining = s.count('data_quality_flag')
if remaining != 1:
    raise SystemExit('data_quality_flag deveria restar 1x, restou %s' % remaining)
if "const statusTxt = t.value_needs_review" not in s:
    raise SystemExit('status canônico ausente')
if 'civilJourneyTotals' not in s:
    raise SystemExit('fallback civil ausente')

p.write_text(s, encoding='utf-8')

for f in [
    '.tmp-review-inspect.txt','.tmp-review-hits.txt','.tmp-status-block.txt',
    '.tmp-jornada-block.txt','.tmp-operational-block.txt','.tmp-jornada-detail.txt',
    '.tmp-status-detail.txt','.tmp-patch-review-cards.py',
    '.github/workflows/inspect-review-cards.yml'
]:
    Path(f).unlink(missing_ok=True)
