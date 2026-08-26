from pathlib import Path
import re

p=Path('index.html')
s=p.read_text(encoding='utf-8')

# Login protegido: gateway server-side + guarda local de UX
pat=r"async function loginEnter\(\) \{.*?\n\}\n\nasync function loginRegister\(\)"
m=re.search(pat,s,re.S)
if not m:
    raise SystemExit('loginEnter block not found')
repl=r'''const _MOB_LOGIN_GUARD_KEY='mob_login_guard_v1';
function mobLoginGuardLoad(){
  try{return JSON.parse(localStorage.getItem(_MOB_LOGIN_GUARD_KEY)||'{"fails":[],"blockedUntil":0}')}catch(e){return{fails:[],blockedUntil:0}}
}
function mobLoginGuardSave(g){try{localStorage.setItem(_MOB_LOGIN_GUARD_KEY,JSON.stringify(g))}catch(e){}}
function mobLoginBlockedSeconds(){const g=mobLoginGuardLoad();return Math.max(0,Math.ceil(((g.blockedUntil||0)-Date.now())/1000));}
function mobLoginGuardFail(){
  const now=Date.now(),g=mobLoginGuardLoad();
  g.fails=(g.fails||[]).filter(t=>now-t<10*60*1000);g.fails.push(now);
  if(g.fails.length>=5){g.blockedUntil=now+15*60*1000;g.fails=[];}
  mobLoginGuardSave(g);return mobLoginBlockedSeconds();
}
function mobLoginGuardClear(){try{localStorage.removeItem(_MOB_LOGIN_GUARD_KEY)}catch(e){}}

async function loginEnter() {
  const email=document.getElementById('l-email')?.value?.trim();
  const pass=document.getElementById('l-pass')?.value;
  lsErr('l-err','');
  if(!email||!pass){lsErr('l-err','Preencha email e senha');return;}
  const blocked=mobLoginBlockedSeconds();
  if(blocked>0){lsErr('l-err',`Muitas tentativas. Aguarde ${Math.ceil(blocked/60)} min e tente novamente.`);return;}
  lsBtn('l-btn-enter','Entrando...',true);
  try{
    if(_MOB_IS_TEST_ENV){
      const result=await Promise.race([
        _SUPA.auth.signInWithPassword({email,password:pass}),
        new Promise((_,rej)=>setTimeout(()=>rej(new Error('timeout')),12000))
      ]);
      if(result.error) throw new Error('invalid_credentials');
    }else{
      const ctl=new AbortController();const to=setTimeout(()=>ctl.abort(),12000);let resp;
      try{
        resp=await fetch(`${_MOB_SUPA_CONFIG.url}/functions/v1/auth-login-gate`,{
          method:'POST',signal:ctl.signal,
          headers:{'Content-Type':'application/json','apikey':_MOB_SUPA_CONFIG.key},
          body:JSON.stringify({email,password:pass})
        });
      }finally{clearTimeout(to);}
      const data=await resp.json().catch(()=>({}));
      if(!resp.ok){
        if(resp.status===429){
          const mins=Math.max(1,Math.ceil((Number(data.retry_after)||900)/60));
          lsErr('l-err',`Muitas tentativas. Aguarde ${mins} min e tente novamente.`);
          return;
        }
        mobLoginGuardFail();
        lsErr('l-err','Email ou senha inválidos.');
        return;
      }
      const set=await _SUPA.auth.setSession({access_token:data.access_token,refresh_token:data.refresh_token});
      if(set.error)throw new Error('session_error');
    }
    mobLoginGuardClear();
  }catch(err){
    if(String(err?.message||'').includes('invalid_credentials'))mobLoginGuardFail();
    lsErr('l-err',err?.name==='AbortError'?'Tempo esgotado. Verifique sua conexão.':'Não foi possível entrar. Verifique seus dados e tente novamente.');
  }finally{lsBtn('l-btn-enter','Entrar',false);}
}

async function loginRegister()'''
s=s[:m.start()]+repl+s[m.end():]

s=s.replace("if (!pass||pass.length<6) { lsErr('r-err','Senha deve ter pelo menos 6 caracteres'); return; }",
            "if (!pass||pass.length<10) { lsErr('r-err','Use uma senha com pelo menos 10 caracteres'); return; }")
s=s.replace("lsErr('r-err', 'Este email já possui conta. Use \"← Voltar\" → \"Entrar\". Se esqueceu a senha, toque em \"Esqueci minha senha\".');",
            "lsErr('r-err', 'Não foi possível criar a conta com esses dados. Se você já possui cadastro, use Entrar ou Esqueci minha senha.');")
s=s.replace("lsErr('r-err', 'Senha deve ter pelo menos 6 caracteres.');",
            "lsErr('r-err', 'Use uma senha com pelo menos 10 caracteres.');")
s=s.replace('id="l-email" type="email" inputmode="email"','id="l-email" type="email" inputmode="email" autocomplete="email"')
s=s.replace('id="l-pass" type="password"','id="l-pass" type="password" autocomplete="current-password"')

# Informes: cidade atual e locais realmente próximos
s=s.replace('<span id="inf-city-name">Rio de Janeiro</span>','<span id="inf-city-name">Localizando…</span>')
s=s.replace("let _infCity = JSON.parse(localStorage.getItem('sm_inf_city') || '{\"name\":\"Rio de Janeiro\",\"uf\":\"RJ\"}');",
            "let _infCity = JSON.parse(localStorage.getItem('sm_inf_city') || '{\"name\":\"Localizando…\",\"uf\":\"\"}');\nlet _infGps=null;")

old_render="""function renderInformes(){
  infCarregarContagens();
  infRenderBairrosTab();
  infRenderVenueLists();
  infCarregarFeedAgora();
}"""
if old_render not in s:
    raise SystemExit('renderInformes not found')
new_render=r'''function renderInformes(){
  const cityEl=document.getElementById('inf-city-name');
  if(cityEl)cityEl.textContent=(_infCity?.name&&_infCity.name!=='Rio de Janeiro')?_infCity.name:'Localizando…';
  infCarregarContagens();
  infRenderBairrosTab();
  infRenderVenueLists();
  infCarregarFeedAgora();
  infSyncCidadeAtual();
}

function infCityKey(name){
  const n=(name||'').trim();
  if(/^rio de janeiro$/i.test(n))return'rio';
  return n.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||null;
}

async function infReverseCidade(lat,lon){
  try{
    const u=`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&zoom=10&addressdetails=1&accept-language=pt-BR`;
    const r=await fetch(u,{headers:{Accept:'application/json'}});if(!r.ok)throw new Error('reverse');
    const d=await r.json(),a=d.address||{};
    const name=a.city||a.town||a.municipality||a.village||a.county;
    const iso=a['ISO3166-2-lvl4']||a['ISO3166-2-lvl6']||'';
    return name?{name,uf:(iso.split('-')[1]||'').toUpperCase()}:null;
  }catch(e){return null;}
}

async function infSyncCidadeAtual(){
  if(!navigator.geolocation)return;
  navigator.geolocation.getCurrentPosition(async pos=>{
    const lat=pos.coords.latitude,lon=pos.coords.longitude;_infGps={lat,lon,at:Date.now()};
    const city=await infReverseCidade(lat,lon);
    if(city){_infCity=city;localStorage.setItem('sm_inf_city',JSON.stringify(_infCity));const el=document.getElementById('inf-city-name');if(el)el.textContent=city.name;}
    else{const el=document.getElementById('inf-city-name');if(el&&_infCity?.name)el.textContent=_infCity.name;}
    try{await _SUPA?.rpc('ensure_venues_for_region',{p_lat:lat,p_lng:lon});}catch(e){}
    infRenderNearbyVenueLists(lat,lon);
  },()=>{const el=document.getElementById('inf-city-name');if(el)el.textContent=_infCity?.name||'Escolher cidade';},{enableHighAccuracy:true,timeout:10000,maximumAge:60000});
}

async function infRenderNearbyVenueLists(lat,lon){
  const q=`[out:json][timeout:18];(`+
    `nwr(around:7000,${lat},${lon})[shop=mall][name];`+
    `nwr(around:1800,${lat},${lon})[amenity~"^(bar|pub|restaurant|cafe|nightclub)$"][name];`+
    `nwr(around:6000,${lat},${lon})[tourism~"^(hotel|hostel|motel|guest_house)$"][name];`+
    `nwr(around:10000,${lat},${lon})[amenity~"^(theatre|cinema|arts_centre|events_venue)$"][name];`+
    `nwr(around:10000,${lat},${lon})[leisure=stadium][name];`+
    `nwr(around:7000,${lat},${lon})[tourism~"^(museum|attraction|viewpoint|gallery)$"][name];`+
    `);out center 300;`;
  try{
    const r=await fetch(`https://overpass-api.de/api/interpreter?data=${encodeURIComponent(q)}`);if(!r.ok)throw new Error('overpass');
    const d=await r.json(),groups={shoppings:[],bares:[],hoteis:[],eventos:[],turistico:[]};
    const R=6371,toRad=x=>x*Math.PI/180;
    const dist=(a,b,c,dd)=>{const dl=toRad(c-a),dn=toRad(dd-b),x=Math.sin(dl/2)**2+Math.cos(toRad(a))*Math.cos(toRad(c))*Math.sin(dn/2)**2;return R*2*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));};
    for(const e of(d.elements||[])){
      const t=e.tags||{},n=t.name;if(!n)continue;const elat=e.lat??e.center?.lat,elon=e.lon??e.center?.lon;if(elat==null||elon==null)continue;
      let cat=null;
      if(t.shop==='mall')cat='shoppings';
      else if(/^(bar|pub|restaurant|cafe|nightclub)$/.test(t.amenity||''))cat='bares';
      else if(/^(hotel|hostel|motel|guest_house)$/.test(t.tourism||''))cat='hoteis';
      else if(/^(theatre|cinema|arts_centre|events_venue)$/.test(t.amenity||'')||t.leisure==='stadium')cat='eventos';
      else if(/^(museum|attraction|viewpoint|gallery)$/.test(t.tourism||''))cat='turistico';
      if(!cat)continue;const km=dist(lat,lon,elat,elon);
      groups[cat].push({n,sub:t['addr:suburb']||t['addr:city']||(km<1?`${Math.round(km*1000)} m`:`${km.toFixed(1)} km`),km});
    }
    for(const[cat,items0]of Object.entries(groups)){
      const items=[...new Map(items0.sort((a,b)=>a.km-b.km).map(x=>[x.n.toLowerCase(),x])).values()].slice(0,12);
      infRenderNearbyVenueTab(cat,items);
    }
    infCarregarBadgesListagem();
  }catch(e){console.warn('locais próximos',e);}
}

function infRenderNearbyVenueTab(cat,items){
  const el=document.getElementById('inf-vlist-'+cat);if(!el)return;const v=INF_VENUES[cat];if(!v)return;const t=INF_TIPOS[v.tipo]||INF_TIPOS.bairro;
  if(!items.length){el.innerHTML='<div class="inf-empty">Nenhum local próximo encontrado</div>';return;}
  el.innerHTML=items.map(item=>`<div class="inf-vitem" onclick="infAbrirLocal(this,'${item.n.replace(/'/g,"\\'")}','${v.tipo}')"><div class="inf-vitem-ic" style="background:${t.bg}">${infIconSvg(v.tipo,t.cor,15)}</div><div><div class="inf-vitem-name">${item.n}</div><div class="inf-vitem-sub">${item.sub||''}</div></div><div class="inf-vitem-badges" data-vname="${esc(item.n)}"></div><div class="inf-vitem-ct z">–</div></div>`).join('');
}'''
s=s.replace(old_render,new_render)

pat_city=r"function infEscolherCidade\(name, uf\)\{.*?\n\}"
m=re.search(pat_city,s,re.S)
if not m:
    raise SystemExit('infEscolherCidade not found')
repl_city=r'''async function infEscolherCidade(name, uf){
  _infCity={name,uf};localStorage.setItem('sm_inf_city',JSON.stringify(_infCity));document.getElementById('inf-city-name').textContent=name;closeMo('mo-inf-cidade');
  try{
    const u=`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=br&q=${encodeURIComponent(name+', '+uf+', Brasil')}`;
    const r=await fetch(u,{headers:{Accept:'application/json'}}),d=await r.json();
    if(d?.[0]){const lat=Number(d[0].lat),lon=Number(d[0].lon);_infGps={lat,lon,at:Date.now()};infRenderNearbyVenueLists(lat,lon);}
  }catch(e){}
  try{infCarregarFeedAgora?.();}catch(e){}
}'''
s=s[:m.start()]+repl_city+s[m.end():]

s=s.replace("city:'rio',param_type:_infRepTipo","city:infCityKey(_infCity?.name),param_type:_infRepTipo")

checks=['auth-login-gate','infSyncCidadeAtual','infRenderNearbyVenueLists','Email ou senha inválidos.']
for c in checks:
    if c not in s: raise SystemExit(f'missing after patch: {c}')
if "city:'rio',param_type:_infRepTipo" in s: raise SystemExit('fixed rio insert remains')

p.write_text(s,encoding='utf-8')
print('patched',len(s))
