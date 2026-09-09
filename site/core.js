export const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const norm=s=>String(s||'').normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase();
export const money=n=>n==null?'—':new Intl.NumberFormat('ca-ES',{style:'currency',currency:'EUR',maximumFractionDigits:2}).format(n);
export const compact=n=>n==null?'—':n>=1e6?(n/1e6).toLocaleString('ca-ES',{maximumFractionDigits:2})+' M€':money(n);
export function madridTime(s){if(!s)return NaN;if(/Z$|[+-]\d\d:\d\d$/.test(s))return Date.parse(s);if(s.length===10)return NaN;const wall=Date.parse(s+'Z');if(!Number.isFinite(wall))return NaN;let value=wall;for(let i=0;i<3;i++){let p=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value)).map(x=>[x.type,x.value]));value+=wall-Date.UTC(+p.year,+p.month-1,+p.day,+p.hour,+p.minute,+p.second);}return value;}
export function date(s,withTime=false){let n=withTime?madridTime(s):Date.parse(s?.length===10?s+'T12:00:00Z':s);return Number.isFinite(n)?new Intl.DateTimeFormat('ca-ES',{dateStyle:'medium',...(withTime?{timeStyle:'short'}:{}),timeZone:'Europe/Madrid'}).format(new Date(n)):'—';}
export function safeUrl(s){try{let u=new URL(s);return u.protocol==='https:'?u.href:'#';}catch{return '#';}}
export function stage(r,now=Date.now()){
 if(r.isSystem)return 'system';
 if(/suspens|suspendid/i.test((r.phase||'')+' '+(r.title||'')))return 'suspended';
 if(/Anul|Desert|Desist|Renún|Resolt|Execuci|Finalitzat/i.test(r.phase||''))return 'closed';
 if(['Adjudicació','Formalització'].includes(r.phase))return 'awarded';
 if(/avaluació/i.test(r.phase||''))return 'pending';
 if(/previ|futura|consulta/i.test(r.phase||''))return 'planned';
 if(r.phase==='Anunci de licitació'){let t=madridTime(r.deadline);return t>now?'open':Number.isFinite(t)?'pending':'unknown';}
 return 'unknown';
}
export const labels={open:'Oberta',pending:'Pendent d’adjudicació',awarded:'Adjudicada',closed:'Tancada',suspended:'Suspesa',planned:'Anunci previ',system:'Adhesió SDA',unknown:'Sense termini'};
export function countdown(r,now=Date.now()){let state=stage(r,now),hours=(madridTime(r.deadline)-now)/36e5;if(state!=='open')return {number:labels[state],unit:state==='awarded'?date(r.awardDate):'',className:'status'};return {number:hours<24?Math.max(1,Math.ceil(hours)):Math.ceil(hours/24),unit:hours<24?'hores':'dies',className:hours<=72?'urgent':hours<=168?'warn':''};}
export function criteriaType(c){const s=norm(c.label);if(c.kind==='technical')return 'technical';if(c.kind==='automatic')return /preu|precio|econom/.test(s)?'price':'automatic';return /judici|juicio|tecnic/.test(s)&&!/autom/.test(s)?'technical':/preu|precio|econom/.test(s)?'price':'automatic';}
export function dossierModel(r,d={},pdf={}){const t=d.terms||{},criteria=(pdf.reviewedCriteria||t.criteria||[]).map(c=>({...c,children:[...(c.children||[])]}));let technical=criteria.find(c=>criteriaType(c)==='technical');const blocks=pdf.technicalBlocks||[];if(!pdf.reviewedCriteria&&technical&&blocks.length&&Math.abs(blocks.reduce((a,b)=>a+b.weight,0)-technical.weight)<.011)technical.children=blocks;
 let extension=t.extensionAllowed===false?0:null,modification=t.modificationAllowed===false?0:null;for(let e of d.singleLot?pdf.economicRows||[]:[]){if(/prorro/i.test(norm(e.label))&&t.extensionAllowed!==false)extension=e.amount;if(/modific/i.test(norm(e.label))&&t.modificationAllowed!==false)modification=e.amount;}
 return {r,d,pdf,criteria,duration:(t.duration||r.duration||'—').replace(/\b1 anys\b/g,'1 any').replace(/\b1 mesos\b/g,'1 mes'),extension,modification,withExtensions:extension!=null&&r.budget!=null?r.budget+extension:null,vec:t.vec??r.vec,technicalTotal:criteria.filter(c=>criteriaType(c)==='technical').reduce((s,c)=>s+(Number(c.weight)||0),0),facts:pdf.facts||[]};
}
export const csvCell=v=>'"'+String(v??'').replace(/^[\s]*[=+@-]/,"'$&").replace(/"/g,'""')+'"';
