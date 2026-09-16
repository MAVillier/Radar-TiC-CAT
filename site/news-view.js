import {esc,norm,date,safeUrl} from './core.js';
export const newsSections=[
 ['ctti','CTTI','Estratègia, projectes i persones'],
 ['generalitat','Generalitat','Departaments i organismes'],
 ['barcelona','Ajuntament de Barcelona','Tecnologia municipal'],
 ['municipis','Ajuntaments de Catalunya','Transformació digital local'],
 ['diba','Diputació de Barcelona','Serveis i projectes TIC'],
 ['diputacions','Diputacions de Catalunya','Girona, Lleida i Tarragona'],
 ['competition-cat','Competència · Catalunya','Consultores i proveïdors TIC'],
 ['competition-es','Competència · Espanya','Consultores i proveïdors TIC'],
 ['competition-world','Competència · Món','Moviments internacionals'],
 ['balears','Govern Balear','Actualitat TIC']
];
export function selectNews(items,bucket='',query=''){
 const q=norm(query),priority=new Map(newsSections.map(([id],i)=>[id,i]));
 return (items||[]).filter(n=>priority.has(n.bucket)&&typeof n.summary==='string'&&n.summary.trim().length>40&&safeUrl(n.url)!=='#'&&(!bucket||n.bucket===bucket)&&(!q||norm(n.title+' '+n.summary+' '+n.source).includes(q)))
 .sort((a,b)=>priority.get(a.bucket)-priority.get(b.bucket)||(Date.parse(b.published)-Date.parse(a.published)));
}
export function newsHtml(items){
 return newsSections.map(([bucket,label,subtitle])=>{
  const rows=items.filter(n=>n.bucket===bucket);if(!rows.length)return '';
  return `<section class="news-section ${bucket==='ctti'?'news-priority':''}" data-news-section="${bucket}" aria-label="${esc(label)}"><div class="news-section-heading"><div><h2>${esc(label)}</h2><p>${esc(subtitle)}</p></div><span>${rows.length}</span></div><div class="news-grid">${rows.map(n=>`<article class="news-card"><div class="news-meta"><span>${esc(n.source)}</span><time datetime="${esc(n.published)}">${n.dateKind==='updated'?'Actualitzada · ':''}${esc(date(n.published))}</time></div><h3><a href="${esc(safeUrl(n.url))}" target="_blank" rel="noopener">${esc(n.title)}</a></h3><p class="news-summary">${esc(n.summary)}</p><a class="news-link" href="${esc(safeUrl(n.url))}" target="_blank" rel="noopener">Llegeix la notícia ↗</a></article>`).join('')}</div></section>`;
 }).join('');
}
