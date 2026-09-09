import {money,date,labels,stage} from './core.js';

export async function makePdf(m){
 const {PDFDocument,StandardFonts,rgb}=globalThis.PDFLib;
 const pdf=await PDFDocument.create(),font=await pdf.embedFont(StandardFonts.Helvetica),bold=await pdf.embedFont(StandardFonts.HelveticaBold);
 const navy=rgb(0,0,.36),blue=rgb(0,.45,.9),ink=rgb(.1,.13,.2),muted=rgb(.42,.46,.52),light=rgb(.92,.94,.97);
 let page,y;const W=595,H=842,L=46,R=549;
 const clean=s=>String(s??'—').replace(/[↗↓←→★☆]/g,'').replace(/\u202f|\u00a0/g,' ').replace(/[^\x20-\x7e\xa0-\xff€–—‘’“”…]/g,'');
 function text(s,x,at,size=10,f=font,color=ink){page.drawText(clean(s),{x,y:at,size,font:f,color});}
 function newPage(){page=pdf.addPage([W,H]);page.drawRectangle({x:0,y:H-9,width:W,height:9,color:navy});text('RADAR / SECTOR PÚBLIC',L,H-43,9,bold,navy);text(m.r.exp,R-bold.widthOfTextAtSize(clean(m.r.exp),9),H-43,9,bold,muted);y=H-78;}
 function need(h){if(y-h<57)newPage();}
 function lines(s,width,size=10,f=font){let out=[],line='';for(const word of clean(s).split(/\s+/)){let candidate=line?line+' '+word:word;if(f.widthOfTextAtSize(candidate,size)>width&&line){out.push(line);line=word;}else line=candidate;}if(line)out.push(line);return out;}
 function paragraph(s,{size=10,f=font,color=ink,width=R-L,gap=8}={}){for(const line of lines(s,width,size,f)){need(size*1.5);text(line,L,y,size,f,color);y-=size*1.5;}y-=gap;}
 function section(n,title){need(54);y-=10;text(n,L,y,10,bold,blue);text(title,L+28,y,14,bold,navy);y-=27;}
 function pair(label,value){const ls=lines(value,R-L-172,10,bold),left=lines(label,155,9),height=Math.max(26,Math.max(ls.length,left.length)*14+9);need(height);left.forEach((s,i)=>text(s,L,y-i*14,9,font,muted));ls.forEach((s,i)=>text(s,L+172,y-i*14,10,bold));y-=height;}
 newPage();paragraph(m.r.shortTitle,{size:24,f:bold,color:navy,gap:6});paragraph(m.r.organ,{size:10,color:muted});
 paragraph((m.r.sdaParent?'INVITACIÓ SDA · ':'')+labels[stage(m.r)]+' · '+(m.r.lot?'Lot '+m.r.lot+' · ':'')+'Dossier '+date(new Date().toISOString()),{size:9,color:blue});
 section('01','Economia / sense IVA');
 const cells=[['Import inicial',money(m.r.budget)],['Pròrrogues',money(m.extension)],['Base + pròrrogues',money(m.withExtensions)],['Modificacions previstes',money(m.modification)],['Valor estimat total',money(m.vec)],['Adjudicació',money(m.r.awarded)]];
 for(let i=0;i<cells.length;i+=2){need(65);cells.slice(i,i+2).forEach(([label,value],j)=>{let x=L+j*260;page.drawRectangle({x,y:y-47,width:243,height:61,color:light});text(label,x+12,y-4,9,font,muted);text(value,x+12,y-28,17,bold,navy);});y-=73;}
 pair('Durada inicial',m.duration);pair('Termini de presentació',date(m.r.deadline,true));
 pair('Pròrrogues',m.d.terms?.extensionAllowed===false?'No previstes':m.d.terms?.extensionText||'—');
 pair('Modificacions',m.d.terms?.modificationAllowed===false?'No previstes':m.d.terms?.modificationText||'—');
 const scoreHeight=65+m.criteria.reduce((n,c)=>n+Math.max(26,lines(c.label,155,9).length*14+9)+(c.children||[]).reduce((s,x)=>s+lines(x.label+' / '+(x.weight??'—')+' punts',R-L,9).length*14+3,0),0);
 if(scoreHeight>y-57&&m.criteria.length)newPage();
 section('02','Repartiment de punts');
 if(!m.criteria.length)paragraph('Criteris al plec enllaçat.',{color:muted});
 for(const c of m.criteria){need(Math.min(300,55+(c.children||[]).reduce((n,x)=>n+lines(x.label+' / '+(x.weight??'—')+' punts',R-L,9).length*14+3,0)));pair(c.label,(c.weight??'—')+' punts');for(const child of c.children||[]){paragraph(child.label+'  /  '+(child.weight??'—')+' punts',{size:9,color:muted,gap:3});}}
 section('03','Preparació de l’oferta');
 pair('Oferta tècnica',m.criteria.length?(m.technicalTotal?m.technicalTotal+' punts de judici de valor':'Sense punts de judici de valor'):'—');
 if(m.r.categories?.length)pair('Categoria SDA',m.r.categories.join(' · '));
 for(const f of m.facts)pair(f.label,f.text);
 for(const r of (m.d.terms?.technicalRequirements||[]).slice(0,4))paragraph(r.label+(r.minimum?' · '+r.minimum:''),{size:9});
 if(m.r.winner){section('04','Resultat');pair('Adjudicatari',m.r.winner);pair('Data',date(m.r.awardDate));pair('Diferència d’import',m.r.discount?.value==null?'—':m.r.discount.value+' %');}
 section('↗','Consulta');need(20);text('Obre la publicació oficial i els plecs',L,y,10,bold,blue);
 if(/^https:\/\//.test(m.r.source)){const {PDFName,PDFString}=globalThis.PDFLib;const annotation=pdf.context.obj({Type:'Annot',Subtype:'Link',Rect:[L,y-3,R,y+13],Border:[0,0,0],A:{Type:'Action',S:'URI',URI:PDFString.of(m.r.source)}});page.node.set(PDFName.of('Annots'),pdf.context.obj([pdf.context.register(annotation)]));}y-=25;
 pdf.getPages().forEach((p,i)=>{page=p;text('RADAR · Imports sense IVA',L,29,8,font,muted);text((i+1)+' / '+pdf.getPageCount(),R-30,29,8,font,muted);});
 pdf.setTitle(m.r.shortTitle);pdf.setAuthor('Radar TIC');pdf.setSubject(m.r.exp);return pdf.save();
}
