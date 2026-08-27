const fs = require('fs');
const src = fs.readFileSync('index.html','utf8');
const start = src.indexOf('function resolveTimeConflicts(list)');
const end = src.indexOf('function applyDetails', start);
if(start < 0 || end < 0) throw new Error('resolveTimeConflicts not found');
const fn = src.slice(start,end);
function normalizeTime(v){ const m=String(v||'').match(/(\d{1,2}):(\d{2})/); return m ? String(Number(m[1])).padStart(2,'0')+':'+m[2] : ''; }
function round2(v){ return Math.round((Number(v)||0)*100)/100; }
function timeToMinutes(t){ const [h,m]=normalizeTime(t).split(':').map(Number); return h*60+m; }
function mergeFields(a,b){ for(const [k,v] of Object.entries(b||{})){ if((a[k]===undefined||a[k]===null||a[k]==='') && v!==undefined&&v!==null&&v!=='') a[k]=v; } return a; }
eval(fn);
const expected = [
 ['10:11',7.90,'App'],['10:11',8.60,'Dinheiro'],['09:57',10.70,'App'],['09:44',8.70,'Dinheiro'],
 ['09:34',10.10,'App'],['09:04',9.60,'Dinheiro'],['08:55',13.50,'App'],['08:41',14.60,'App'],
 ['08:32',13.50,'Dinheiro'],['08:17',10.10,'Dinheiro'],['08:03',18.20,'App'],['07:51',22.70,'App'],['07:33',22.90,'App']
].map(([time,value,payment])=>({time,value,payment}));
const raw = [
 ...expected,
 {time:'10:11',value:7.90,payment:'App',origin:'leitura complementar'},
 {time:'08:03',value:18.20,payment:'App',destination:'leitura complementar'},
 {time:'07:36',value:-16.98,category:'Outro',payment:'App'}
];
const out = resolveTimeConflicts(raw);
if(out.length !== 13) throw new Error(`expected 13 rides, got ${out.length}`);
const at1011=out.filter(x=>x.time==='10:11').map(x=>x.value).sort((a,b)=>a-b);
if(JSON.stringify(at1011)!==JSON.stringify([7.9,8.6])) throw new Error('two distinct rides at 10:11 were not preserved');
if(!out.some(x=>x.time==='08:03' && Math.abs(x.value-18.2)<0.001)) throw new Error('08:03 R$18.20 missing');
if(out.some(x=>Number(x.value)<=0 || String(x.category||'').toLowerCase()==='outro')) throw new Error('financial adjustment leaked into rides');
for(let i=1;i<out.length;i++) if(timeToMinutes(out[i-1].time)<timeToMinutes(out[i].time)) throw new Error('rides are not sorted by textual time');
if(!src.includes('const sameTimeCandidates = unique.filter')) throw new Error('same-minute detail disambiguation missing');
if(!src.includes('const fareDiff = Math.abs(fare - trip.value);')) throw new Error('automatic-trip value matching hardening missing');
console.log('PASS: 13 rides; duplicate frames merged; both 10:11 rides preserved; R$18.20 preserved; -R$16.98 rejected; order validated.');
