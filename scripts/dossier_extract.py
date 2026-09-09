"""Extract concise, traceable document facts. Never assume a standard extension or 20%."""
import concurrent.futures,datetime as dt,hashlib,io,json,os,re,urllib.request
from pypdf import PdfReader
from refresh import ROOT
D=ROOT/'site/data'
def flat(s):return re.sub(r'\s+',' ',s).strip()
def euro(s):return float(s.replace('.','').replace(',','.'))
def extract_pages(pages):
 out={'technicalBlocks':[],'economicRows':[],'facts':[],'scorePages':[]}
 for p,normal,layout in pages:
  text=flat(normal)
  if re.search(r'criteris.*judici de valor',text,re.I) and re.search(r'\d+\s+punts',text,re.I):out['scorePages'].append(p)
  for m in re.finditer(r'Criteris relacionats amb\s+(Soluci[óo]\s+.{2,65}?)\s+(\d+(?:,\d+)?)\s+punts',text,re.I):
   out['technicalBlocks'].append({'label':m[1].strip(),'weight':float(m[2].replace(',','.')),'page':p})
  for line in layout.splitlines():
   m=re.search(r'^\s*(Pr[òo]rrogues?(?:\s+[^\d]{0,40})?|Modificacions?(?:\s+[^\d]{0,40})?|Import\s+(?:de\s+)?(?:les\s+)?pr[òo]rrogues?|Import\s+(?:de\s+)?(?:les\s+)?modificacions?)\s{2,}([\d.]+,\d{2})\s*(?:€|euros)?',line,re.I)
   if m:out['economicRows'].append({'label':flat(m[1]),'amount':euro(m[2]),'page':p})
  for pattern,label in [(r'(?:extensi[óo]|extensi[óo] m[àa]xima|m[àa]xim)\s+(?:de\s+)?(\d+)\s+p[àa]gines','Extensió de l’oferta'),(r'(?:llindar m[íi]nim|puntuaci[óo] m[íi]nima)[^.]{0,90}?\d+(?:[,.]\d+)?\s+punts','Llindar tècnic')]:
   m=re.search(pattern,text,re.I)
   if m:out['facts'].append({'label':label,'text':m[0],'page':p})
 out['technicalBlocks']=list({(x['label'].lower(),x['weight']):x for x in out['technicalBlocks']}.values())
 out['economicRows']=list({(x['label'].lower(),x['amount']):x for x in out['economicRows']}.values())
 out['facts']=list({(x['label'],x['text']):x for x in out['facts']}.values())[:5]
 return out
def main():
 dossiers=json.loads((D/'dossiers.json').read_text(encoding='utf-8'));target=D/'executive.json';old=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
 def choose(d):
  files=d.get('attachments',[])
  return next((a for term in ('invitaci','quadre','pcap','administrativ') for a in files if term in a['title'].lower()),None)
 jobs=[];out={}
 for id,d in dossiers.items():
  doc=choose(d)
  if not doc:continue
  if id in old and old[id].get('url')==doc['url'] and old[id].get('status')=='ok':out[id]=old[id]
  else:jobs.append((id,doc))
 jobs.sort(key=lambda j:(0 if 'invitaci' in j[1]['title'].lower() else 1,j[0]))
 def process(job):
  id,doc=job
  try:
   with urllib.request.urlopen(urllib.request.Request(doc['url'],headers={'User-Agent':'RadarTIC/3.0'}),timeout=45) as r:
    b=r.read(18_000_001)
   if len(b)>18_000_000:raise ValueError('Document massa gran')
   reader=PdfReader(io.BytesIO(b));pages=[]
   for i,p in enumerate(reader.pages[:90]):
    normal=p.extract_text() or ''
    # Layout extraction is only necessary for the small economic tables.
    layout=p.extract_text(extraction_mode='layout') if re.search(r'valor estimat|dades econ.miques|pr.rrogues|modificacions',normal,re.I) else normal
    pages.append((i+1,normal,layout))
   facts=extract_pages(pages)
   return id,dict(facts,status='ok',url=doc['url'],title=doc['title'],sha256=hashlib.sha256(b).hexdigest(),pages=len(reader.pages),readPages=len(pages),fetched=dt.datetime.now(dt.timezone.utc).isoformat())
  except Exception as e:return id,{'status':'error','url':doc['url'],'error':type(e).__name__}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for i,(id,v) in enumerate(pool.map(process,jobs[:int(os.environ.get('DOSSIER_LIMIT','100'))])):
   out[id]=v
   if i%20==0:print('Dossiers PDF',i+1,flush=True)
 reviewed=json.loads((D/'reviewed-dossiers.json').read_text(encoding='utf-8')) if (D/'reviewed-dossiers.json').exists() else {}
 for value in out.values():
  if value.get('sha256') in reviewed:value.update(reviewed[value['sha256']])
 target.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 print('Extracció executiva:',len(out),'; correctes:',sum(v['status']=='ok' for v in out.values()),flush=True)
if __name__=='__main__':main()
