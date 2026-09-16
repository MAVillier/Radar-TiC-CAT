"""Field-level PDF evidence. Missing text is never proof of absence."""
import concurrent.futures,datetime as dt,gzip,hashlib,io,json,os,re,urllib.request
from pathlib import Path
from pypdf import PdfReader
from zoneinfo import ZoneInfo
from contract_terms import extract_terms
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'site/data';VERSION=2
def flat(s):return re.sub(r'\s+',' ',s).strip()
def candidates(d):
 docs=d.get('attachments',[]);out=[]
 for pattern in (r'invitaci|quadre|pcap|administrativ|(?:^|[^a-z])qc(?:$|[^a-z])',r'mem[oò]ria|memoj|justifica|informe.*necessitat'):
  for a in docs:
   if re.search(pattern,a.get('title',''),re.I) and a['url'] not in [x['url'] for x in out]:out.append(a)
 return out
def extract(pages):
 evidence=extract_terms(pages)
 # These expressions require an actual provision, not a generic conditional clause.
 positive=r'(?:per aquesta contractaci[oó][^.]{0,180}?(?:pr[oò]rroga[^.]{0,60}|any de pr[oò]rroga)|(?:s.admet|es preveu|est[aà] prevista)\s+(?:la\s+)?(?:possibilitat[^.]{0,100})?pr[oò]rroga[^.]{0,100})'
 negative=r'(?:^|[.\n])\s*(?:No es preveu(?:en)?|No s.admet(?:en)?|No est[aà] prevista)\s+(?:cap\s+|la\s+|les\s+)?pr[oò]rrog(?:a|ues)\s*[.]'
 for item in pages:
  i,text=item[:2]
  s=flat(text)
  for match in re.finditer(positive,s,re.I):
   quote=match.group(0)
   if re.search(r'\bsi\s+(?:aix[ií]|es|s.ha)|no\s+(?:es|s.admet|est[aà])',quote,re.I):continue
   evidence.append({'field':'extensionAllowed','value':True,'text':quote[:280],'page':i,'scope':'contract' if re.search(r'per aquesta contractaci',quote,re.I) else 'unspecified'})
  for match in re.finditer(negative,text,re.I):evidence.append({'field':'extensionAllowed','value':False,'text':flat(match[0]),'page':i,'scope':'unspecified'})
 return evidence
def resolve(r,d,documents,reviews):
 fields={};evidence=[];conflicts=[]
 for doc in documents:
  for ev in doc.get('evidence',[]):
   if d.get('singleLot') or ev['scope']=='contract':evidence.append(dict(ev,url=doc['url'],sha256=doc['sha256']))
  review=reviews.get(doc.get('sha256',''),{}).get(str(r.get('lot') or ''))
  if review and review['budget']==r.get('budget') and review['vec']==r.get('vec'):
   for field,value in review['fields'].items():evidence.append({'field':field,'value':value,'page':review['pages'],'url':doc['url'],'sha256':doc['sha256'],'scope':'lot','reviewed':True})
 for field in {x['field'] for x in evidence}:
  evs=[e for e in evidence if e['field']==field];values={json.dumps(e['value'],sort_keys=True) for e in evs}
  if len(values)==1:fields[field]=evs[0]['value']
  else:conflicts.append(field)
 if fields.get('extensionAllowed') is True and 'extensionText' not in fields:
  fields['extensionText']=next((e['text'] for e in evidence if e['field']=='extensionAllowed' and e.get('text')),'Prevista')
 if fields.get('extensionCount') and fields.get('extensionMonthsEach'):
  fields['extensionText']=f"{fields['extensionCount']} pròrrogues de {fields['extensionMonthsEach']} mesos cadascuna"
 if fields.get('durationMonths') and 'duration' not in fields:fields['duration']=f"{fields['durationMonths']} mesos"
 if fields.get('modificationAmount') is not None and r.get('budget') and 'modificationText' not in fields:
  fields['modificationText']=f"{fields['modificationAmount']/r['budget']*100:.2f}% de l’import inicial".replace('.00%','%')
 # A monetary breakdown must reconcile with the official net VEC; never infer a missing amount from the gap.
 if all(fields.get(k) is not None for k in ('extensionAmount','modificationAmount')) and r.get('budget') is not None and r.get('vec') is not None:
  if abs(r['budget']+fields['extensionAmount']+fields['modificationAmount']-r['vec'])>.03:
   conflicts.append('economicBreakdown')
   for k in ('extensionAmount','modificationAmount'):fields.pop(k,None)
 structured=d.get('terms',{})
 for field in ('extensionAllowed','modificationAllowed'):
  if field in fields and structured.get(field) is not None and fields[field]!=structured[field]:conflicts.append('publication:'+field)
 return {'version':VERSION,'recordHash':r['rawHash'],'fields':fields,'evidence':evidence,'conflicts':conflicts,'documents':[{'url':v['url'],'status':v['status'],'sha256':v.get('sha256'),'pages':v.get('pages')} for v in documents],'checkedAt':dt.datetime.now(dt.timezone.utc).isoformat()}
def main():
 catalog=json.loads(gzip.decompress((D/'catalog.json.gz').read_bytes()));dossiers=json.loads((D/'dossiers.json').read_text(encoding='utf-8'))
 target=D/'document-validation.json';old=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
 reviews=json.loads((D/'document-reviews.json').read_text(encoding='utf-8')) if (D/'document-reviews.json').exists() else {}
 cachefile=D/'document-validation-cache.json';cache=json.loads(cachefile.read_text(encoding='utf-8')) if cachefile.exists() else {}
 now=dt.datetime.now(dt.timezone.utc);rows={r['id']:r for r in catalog['records']}
 out={k:v for k,v in old.items() if k in rows and v.get('recordHash')==rows[k]['rawHash']}
 def is_open(r):
  try:
   deadline=dt.datetime.fromisoformat(r.get('deadline') or '')
   if deadline.tzinfo is None:deadline=deadline.replace(tzinfo=ZoneInfo('Europe/Madrid'))
   return deadline>now
  except ValueError:return False
 active=[r for r in rows.values() if r.get('tic') and not r.get('isSystem') and r['phase']=='Anunci de licitació' and is_open(r) and r['world'] in ('generalitat','local')]
 # Rotate through all active records instead of repeatedly checking only the newest 120.
 active.sort(key=lambda r:(out.get(r['id'],{}).get('checkedAt',''),r['id']))
 jobs=active[:int(os.environ.get('VALIDATION_LIMIT','120'))];docs={a['url']:a for r in jobs for a in candidates(dossiers.get(r['id'],{}))}
 def read(a):
  u=a['url'];prior=cache.get(u,{})
  if prior.get('version')==VERSION and prior.get('status')=='read' and (now-dt.datetime.fromisoformat(prior['fetched'])).total_seconds()<86400:return u,prior
  try:
   with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'RadarTIC/document-verification'}),timeout=35) as response:raw=response.read(20_000_001)
   if len(raw)>20_000_000:raise ValueError('size')
   pdf=PdfReader(io.BytesIO(raw));pages=[]
   for i,p in enumerate(pdf.pages[:150]):
    normal=p.extract_text() or ''
    layout=p.extract_text(extraction_mode='layout') if re.search(r'pr.rrog|modificaci|valor estimat',normal,re.I) else normal
    pages.append((i+1,normal,layout or normal))
   return u,{'version':VERSION,'url':u,'status':'read' if any(t.strip() for _,t,_ in pages) else 'needs_ocr','sha256':hashlib.sha256(raw).hexdigest(),'evidence':extract(pages),'pages':len(pdf.pages),'readPages':len(pages),'fetched':now.isoformat()}
  except Exception as error:return u,{'url':u,'status':'unavailable','error':type(error).__name__}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for i,(u,value) in enumerate(pool.map(read,docs.values())):
   cache[u]=value
   if i%20==0:print('Documents contrastats',i+1,'/',len(docs),flush=True)
 for r in jobs:
  d=dossiers.get(r['id'],{});out[r['id']]=resolve(r,d,[cache[a['url']] for a in candidates(d)],reviews)
 for path,data in [(target,out),(cachefile,cache)]:
  tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(path)
 audit={'generated':now.isoformat(),'active':len(active),'checkedThisRun':len(jobs),'withDocumentFields':sum(bool(v['fields']) for v in out.values()),'conflicts':{k:v['conflicts'] for k,v in out.items() if v['conflicts']},'pending':sum(not out.get(r['id'],{}).get('fields') for r in active)}
 (D/'validation-audit.json').write_text(json.dumps(audit,ensure_ascii=False),encoding='utf-8');print(json.dumps(audit,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
