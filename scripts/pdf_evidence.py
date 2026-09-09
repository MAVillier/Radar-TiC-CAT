"""Extreu pistes de PDFs oficials amb pàgina i empremta. No confirma conclusions."""
import datetime as dt,hashlib,io,json,os,re,urllib.request
from pypdf import PdfReader
from refresh import ROOT

def main():
    path=ROOT/'site/data'; docs=json.loads((path/'documents.json').read_text(encoding='utf-8'))
    target=path/'pdf-evidence.json'; old=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    out={k:v for k,v in old.items() if k in docs and v.get('recordHash')==docs[k].get('recordHash')}
    count=0
    for key,doc in docs.items():
        if key in out:continue
        links=doc.get('attachments',[])
        links=sorted(links,key=lambda x:0 if re.search(r'adj|resol|valor|informe',x['title'],re.I) else 1)
        if not links:continue
        link=links[0]; result={'recordHash':doc['recordHash'],'title':link['title'],'url':link['url'],'fetched':dt.datetime.now(dt.timezone.utc).isoformat(),'reviewed':False,'snippets':[]}
        try:
            req=urllib.request.Request(link['url'],headers={'User-Agent':'RadarTIC/2.0'})
            with urllib.request.urlopen(req,timeout=40) as res: content=res.read(12_000_001)
            if len(content)>12_000_000 or not content.startswith(b'%PDF'):raise ValueError('PDF invàlid o superior a 12 MB')
            result['sha256']=hashlib.sha256(content).hexdigest(); pdf=PdfReader(io.BytesIO(content))
            result['pages']=len(pdf.pages)
            for n,p in enumerate(pdf.pages[:60],1):
                t=re.sub(r'\s+',' ',p.extract_text() or '')
                for m in re.finditer(r'baixa|descompte|incumbent|contracte anterior|preus unitaris|adjudic',t,re.I):
                    clip=t[max(0,m.start()-45):m.start()+140]
                    if not any(s['page']==n and s['text']==clip for s in result['snippets']):result['snippets'].append({'page':n,'text':clip})
                    if len(result['snippets'])>=4:break
                if len(result['snippets'])>=4:break
            result['status']='Text extret automàticament. Cal llegir el PDF complet i verificar el lot.' if result['snippets'] else 'Sense coincidències textuals; pot requerir lectura manual o OCR.'
        except Exception as e:result['status']='Extracció no disponible: '+str(e)[:150]
        out[key]=result;count+=1
        if count>=int(os.environ.get('PDF_LIMIT','8')):break
    target.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('PDFs analitzats',len(out),'amb extractes',sum(bool(v['snippets']) for v in out.values()))
if __name__=='__main__':main()
