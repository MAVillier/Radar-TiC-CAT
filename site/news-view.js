import {esc,norm,date,safeUrl} from './core.js';

export const newsGroups=[
 ['generalitat','CTTI','CTTI · Generalitat i organismes afins',['ctti','generalitat']],
 ['local','AJ','Ajuntaments i diputacions de Catalunya',['barcelona','municipis','diba','diputacions']],
 ['university_hospital','UNI','Universitats · recerca · hospitals',['universitats']],
 ['other','Altres','ICF · MC Mutual · Balears · competència TIC',['icf','mc-mutual','balears','competition-cat','competition-es','competition-world']]
];

export const newsSections=[
 ['ctti','CTTI','Estratègia, projectes i persones'],
 ['generalitat','Generalitat','Departaments i organismes'],
 ['barcelona','Ajuntament de Barcelona','Tecnologia municipal'],
 ['municipis','Ajuntaments de Catalunya','Transformació digital local'],
 ['diba','Diputació de Barcelona','Serveis i projectes TIC'],
 ['diputacions','Diputacions de Catalunya','Girona, Lleida i Tarragona'],
 ['universitats','Universitats i recerca','Universitats · centres de recerca · hospitals'],
 ['icf','ICF','Actualitat TIC i transformació digital'],
 ['mc-mutual','MC Mutual','Tecnologia, serveis i transformació digital'],
 ['balears','Govern Balear','Actualitat TIC'],
 ['competition-cat','Competència · Catalunya','Consultores i proveïdors TIC'],
 ['competition-es','Competència · Espanya','Consultores i proveïdors TIC'],
 ['competition-world','Competència · Món','Moviments internacionals']
];

const sectionByBucket=new Map(newsSections.map(([id,label])=>[id,label]));
const priority=new Map(newsSections.map(([id],i)=>[id,i]));

export function selectNews(items,group='',query=''){
 const q=norm(query),selected=newsGroups.find(([id])=>id===group),allowed=selected?new Set(selected[3]):group?new Set([group]):null;
 return (items||[]).filter(n=>priority.has(n.bucket)&&typeof n.summary==='string'&&n.summary.trim().length>40&&safeUrl(n.url)!=='#'&&(!allowed||allowed.has(n.bucket))&&(!q||norm(n.title+' '+n.summary+' '+n.source+' '+(n.topic||sectionByBucket.get(n.bucket))).includes(q)))
  .sort((a,b)=>priority.get(a.bucket)-priority.get(b.bucket)||(Date.parse(b.published)-Date.parse(a.published)));
}

export function newsHtml(items){
 return newsGroups.map(([id,label,subtitle,buckets])=>{
  const rows=items.filter(n=>buckets.includes(n.bucket));if(!rows.length)return '';
  return `<section class="news-section news-group ${id==='generalitat'?'news-priority':''}" data-news-group="${esc(id)}" aria-label="${esc(label)}"><div class="news-section-heading"><div><h2>${esc(label)}</h2><p>${esc(subtitle)}</p></div><span>${rows.length}</span></div><div class="news-grid">${rows.map(n=>`<article class="news-card" data-news-section="${esc(n.bucket)}"><div class="news-meta"><span>${esc(n.source)}</span><span class="news-topic">${esc(n.topic||sectionByBucket.get(n.bucket))}</span><time datetime="${esc(n.published)}">${n.dateKind==='updated'?'Actualitzada · ':''}${esc(date(n.published))}</time></div><h3><a href="${esc(safeUrl(n.url))}" target="_blank" rel="noopener">${esc(n.title)}</a></h3><p class="news-summary">${esc(n.summary)}</p><a class="news-link" href="${esc(safeUrl(n.url))}" target="_blank" rel="noopener">Llegeix la notícia ↗</a></article>`).join('')}</div></section>`;
 }).join('');
}
