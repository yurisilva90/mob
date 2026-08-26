from pathlib import Path
import re

p=Path('index.html')
s=p.read_text(encoding='utf-8')

# 1. Airport tab: replace fixed GIG/SDU cards with dynamic container.
pat_air=r'''    <!-- ═══ ABA: AEROPORTOS ═══ -->\n    <div class="inf-panelbody hide" id="inf-tab-aero">.*?\n    </div>\n\n    <!-- ═══ ABA: RODOVIÁRIAS ═══ -->'''
m=re.search(pat_air,s,re.S)
if not m:
    raise SystemExit('airport tab block not found')
new_air='''    <!-- ═══ ABA: AEROPORTOS ═══ -->
    <div class="inf-panelbody hide" id="inf-tab-aero">
      <div class="inf-sec-lbl" style="padding-top:2px">Aeroportos em até 200 km</div>
      <div class="inf-vlist" id="inf-vlist-airports"><div class="inf-empty-feed">Localizando aeroportos…</div></div>
    </div>

    <!-- ═══ ABA: RODOVIÁRIAS ═══ -->'''
s=s[:m.start()]+new_air+s[m.end():]

# 2. Neighborhood tab: remove Rio-specific section labels and containers.
pat_bair=r'''    <!-- ═══ ABA: BAIRROS ═══ -->\n    <div class="inf-panelbody hide inf-fill" id="inf-tab-bairros">.*?\n    </div>\n\n    <!-- ═══ ABAS: SHOPPINGS / BARES / HOTÉIS / EVENTOS / TURÍSTICO ═══ -->'''
m=re.search(pat_bair,s,re.S)
if not m:
    raise SystemExit('neighborhood tab block not found')
new_bair='''    <!-- ═══ ABA: BAIRROS ═══ -->
    <div class="inf-panelbody hide inf-fill" id="inf-tab-bairros">
      <div class="inf-area-grp-lbl"><div class="inf-area-grp-dot"></div><span class="inf-area-grp-name" id="inf-bairros-city-label">Bairros da cidade</span></div>
      <div class="inf-bchip-scroll inf-fill-scroll">
        <div class="inf-bchip-2row" id="inf-bairros-dynamic"><div class="inf-empty-feed">Localizando bairros…</div></div>
      </div>
    </div>

    <!-- ═══ ABAS: SHOPPINGS / BARES / HOTÉIS / EVENTOS / TURÍSTICO ═══ -->'''
s=s[:m.start()]+new_bair+s[m.end():]

# 3. Replace fixed neighborhood renderer with neutral loading renderer.
pat_fn=r'''function infRenderBairrosTab\(\)\{.*?\n\}'''
m=re.search(pat_fn,s,re.S)
if not m:
    raise SystemExit('infRenderBairrosTab not found')
new_fn=r'''function infRenderBairrosTab(){
  const label=document.getElementById('inf-bairros-city-label');
  if(label)label.textContent=_infCity?.name&&_infCity.name!=='Localizando…'?`Bairros de ${_infCity.name}`:'Bairros da cidade';
  const el=document.getElementById('inf-bairros-dynamic');
  if(el&&!_infGps)el.innerHTML='<div class="inf-empty-feed">Localizando bairros…</div>';
}'''
s=s[:m.start()]+new_fn+s[m.end():]

# 4. Inject city neighborhoods + 200 km airports helpers before infRenderNearbyVenueLists.
needle='async function infRenderNearbyVenueLists(lat,lon){'
idx=s.find(needle)
if idx<0:
    raise SystemExit('nearby venue loader not found')
helpers=r'''
function infNormText(v){
  return (v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
}
function infDistKm(lat1,lon1,lat2,lon2){
  const R=6371,toRad=x=>x*Math.PI/180;
  const dLat=toRad(lat2-lat1),dLon=toRad(lon2-lon1);
  const a=Math.sin(dLat/2)**2+Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLon/2)**2;
  return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));
}
async function infCidadeBBox(city){
  try{
    const q=[city?.name,city?.uf,'Brasil'].filter(Boolean).join(', ');
    const r=await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=br&addressdetails=1&q=${encodeURIComponent(q)}`,{headers:{Accept:'application/json'}});
    if(!r.ok)throw new Error('nominatim');
    const d=await r.json();
    if(!d?.[0]?.boundingbox)return null;
    const b=d[0].boundingbox.map(Number);
    return {south:b[0],north:b[1],west:b[2],east:b[3]};
  }catch(e){return null;}
}
async function infRenderBairrosCidade(lat,lon,city){
  const el=document.getElementById('inf-bairros-dynamic');
  const label=document.getElementById('inf-bairros-city-label');
  if(label)label.textContent=city?.name?`Bairros de ${city.name}`:'Bairros da cidade';
  if(!el)return;
  el.innerHTML='<div class="inf-empty-feed">Carregando bairros…</div>';
  try{
    const bbox=await infCidadeBBox(city);
    let areaPart;
    if(bbox){areaPart=`(${bbox.south},${bbox.west},${bbox.north},${bbox.east})`;}
    else{areaPart=`(around:30000,${lat},${lon})`;}
    const q=`[out:json][timeout:22];(node${areaPart}[place~"^(suburb|neighbourhood|quarter)$"][name];way${areaPart}[place~"^(suburb|neighbourhood|quarter)$"][name];relation${areaPart}[place~"^(suburb|neighbourhood|quarter)$"][name];);out center tags 180;`;
    const r=await fetch(`https://overpass-api.de/api/interpreter?data=${encodeURIComponent(q)}`);
    if(!r.ok)throw new Error('overpass');
    const d=await r.json();
    const cityNorm=infNormText(city?.name);
    const seen=new Map();
    for(const e of (d.elements||[])){
      const t=e.tags||{},name=(t.name||'').trim();if(!name)continue;
      const addrCity=infNormText(t['addr:city']||t['is_in:city']||'');
      if(cityNorm&&addrCity&&addrCity!==cityNorm)continue;
      const elat=e.lat??e.center?.lat,elon=e.lon??e.center?.lon;
      if(elat==null||elon==null)continue;
      const km=infDistKm(lat,lon,elat,elon);
      const key=infNormText(name);
      const item={n:name,km};
      if(!seen.has(key)||km<seen.get(key).km)seen.set(key,item);
    }
    const items=[...seen.values()].sort((a,b)=>a.km-b.km).slice(0,36);
    if(!items.length){el.innerHTML='<div class="inf-empty-feed">Nenhum bairro encontrado para esta cidade</div>';return;}
    const bic=`<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#475569" stroke-width="2"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 0 1 8 8c0 5.333-8 14-8 14S4 15.333 4 10a8 8 0 0 1 8-8z"/></svg>`;
    el.innerHTML=items.map(x=>`<div class="inf-bchip" onclick="infAbrirLocal(this,'${x.n.replace(/'/g,"\\'")}','bairro')"><div class="inf-bchip-ct z">–</div><div class="inf-bchip-ic">${bic}</div><div class="inf-bchip-name">${x.n}</div></div>`).join('');
    infCarregarContagens();
  }catch(e){console.warn('bairros cidade',e);el.innerHTML='<div class="inf-empty-feed">Não foi possível carregar os bairros agora</div>';}
}
async function infRenderAeroportosRaio(lat,lon){
  const el=document.getElementById('inf-vlist-airports');if(!el)return;
  el.innerHTML='<div class="inf-empty-feed">Buscando aeroportos em até 200 km…</div>';
  try{
    const q=`[out:json][timeout:28];nwr(around:200000,${lat},${lon})[aeroway=aerodrome][name];out center tags 120;`;
    const r=await fetch(`https://overpass-api.de/api/interpreter?data=${encodeURIComponent(q)}`);
    if(!r.ok)throw new Error('overpass');
    const d=await r.json();
    const seen=new Map();
    for(const e of (d.elements||[])){
      const t=e.tags||{},name=(t.name||'').trim();if(!name)continue;
      const elat=e.lat??e.center?.lat,elon=e.lon??e.center?.lon;if(elat==null||elon==null)continue;
      const km=infDistKm(lat,lon,elat,elon);if(km>200.5)continue;
      const iata=(t.iata||'').trim().toUpperCase(),icao=(t.icao||'').trim().toUpperCase();
      const code=iata||icao;
      const city=t['addr:city']||t['addr:municipality']||t['is_in:city']||t['addr:state']||'';
      const passenger=Boolean(iata||t['aerodrome:type']||t.scheduled==='yes'||t.commercial==='yes'||/aeroporto|airport/i.test(name));
      const item={n:name,code,city,km,passenger};
      const key=infNormText(name);
      if(!seen.has(key)||km<seen.get(key).km)seen.set(key,item);
    }
    let items=[...seen.values()];
    const useful=items.filter(x=>x.passenger);
    if(useful.length>=2)items=useful;
    items.sort((a,b)=>(Number(b.passenger)-Number(a.passenger))||(a.km-b.km));
    items=items.slice(0,20);
    if(!items.length){el.innerHTML='<div class="inf-empty-feed">Nenhum aeroporto encontrado em até 200 km</div>';return;}
    const icon=`<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="#0A2F6B" stroke-width="2"><path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg>`;
    el.innerHTML=items.map(a=>{
      const title=a.code?`${a.n} (${a.code})`:a.n;
      const sub=[a.city,a.km<1?`${Math.round(a.km*1000)} m`:`${a.km.toFixed(0)} km`].filter(Boolean).join(' · ');
      return `<div class="inf-vitem" onclick="infAbrirLocal(this,'${title.replace(/'/g,"\\'")}','aero')"><div class="inf-vitem-ic" style="background:#EFF6FF">${icon}</div><div><div class="inf-vitem-name">${title}</div><div class="inf-vitem-sub">${sub}</div></div><div class="inf-vitem-ct z">–</div></div>`;
    }).join('');
    infCarregarContagens();
  }catch(e){console.warn('aeroportos 200km',e);el.innerHTML='<div class="inf-empty-feed">Não foi possível carregar os aeroportos agora</div>';}
}

'''
s=s[:idx]+helpers+s[idx:]

# 5. Extend automatic GPS sync: after city resolved, load all city-aware lists.
old="""    try{await _SUPA?.rpc('ensure_venues_for_region',{p_lat:lat,p_lng:lon});}catch(e){}
    infRenderNearbyVenueLists(lat,lon);"""
new="""    try{await _SUPA?.rpc('ensure_venues_for_region',{p_lat:lat,p_lng:lon});}catch(e){}
    infRenderNearbyVenueLists(lat,lon);
    infRenderBairrosCidade(lat,lon,_infCity);
    infRenderAeroportosRaio(lat,lon);"""
if old not in s:
    raise SystemExit('GPS sync insertion point not found')
s=s.replace(old,new,1)

# 6. Extend manual city selection too.
old2="""    if(d?.[0]){const lat=Number(d[0].lat),lon=Number(d[0].lon);_infGps={lat,lon,at:Date.now()};infRenderNearbyVenueLists(lat,lon);}"""
new2="""    if(d?.[0]){const lat=Number(d[0].lat),lon=Number(d[0].lon);_infGps={lat,lon,at:Date.now()};infRenderNearbyVenueLists(lat,lon);infRenderBairrosCidade(lat,lon,_infCity);infRenderAeroportosRaio(lat,lon);}"""
if old2 not in s:
    raise SystemExit('manual city insertion point not found')
s=s.replace(old2,new2,1)

p.write_text(s,encoding='utf-8')
print('patched city-wide Informes',len(s))
