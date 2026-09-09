"""Compact, unified workspace for the web; evidence remains in expandable dossiers."""
import copy,datetime as dt,gzip,hashlib,json,re,unicodedata
from refresh import ROOT,candidates,discount
D=ROOT/'site/data'
def read(name,default=None):
 p=D/name
 if p.exists():return json.loads(p.read_text(encoding='utf-8'))
 if p.with_suffix(p.suffix+'.gz').exists():return json.loads(gzip.decompress(p.with_suffix(p.suffix+'.gz').read_bytes()))
 return default
def norm(s):return re.sub(r'[^a-z0-9 ]',' ',''.join(c for c in unicodedata.normalize('NFD',str(s).lower()) if unicodedata.category(c)!='Mn'))
def category(title):
 s=norm(title)
 for label,pattern in [('Ciberseguretat',r'ciber|seguretat inform|seguridad inform|firewall|soc\b'),('Cloud',r'cloud|nuvol|nube|datacenter|centre de dades'),('PMO i consultoria',r'\bpmo\b|oficina.*project|consultoria|assessor|governanca'),('Dades i IA',r'intel ligencia|analitica|big data|data lake'),('Telecomunicacions',r'telecom|telefon|connectivitat|fibra|xarxa'),('Suport i operació',r'suport|soporte|operacio|centre de control|helpdesk'),('Equipament',r'equips|equipos|portatils|ordinadors|impressores'),('Aplicacions',r'aplicaci|programari|software|desenvolup|manteniment|licenc|sap|sistema')]:
  if re.search(pattern,s):return label
 return 'Tecnologia'
def short_title(title):
 s=re.sub(r'(?i)^.*?Anunci de licitació del contracte específic\s*:\s*','',title)
 s=re.sub(r'(?i)\s*[-–].*corresponent.*$','',s)
 s=re.sub(r'(?i)^(?:contractació (?:del|de la|de)|serveis? de|subministrament de|contratación (?:del|de la|de)|servicio de)\s+','',s).strip()
 s=re.sub(r'\s+',' ',s).strip()
 s=re.sub(r'(?i)\s+(?:de|per a) (?:la Direcció|el Departament|la Generalitat|l’Ajuntament|la Diputació).*','',s)
 s=s[:1].upper()+s[1:]
 return s if len(s)<=70 else s[:67].rsplit(' ',1)[0]+'…'
def main():
 base=read('radar.json');boards=read('boards.json',{'parents':{}});bal=read('balears.json',{'records':[]});docs=read('documents.json',{});mapping=read('organ-map.json',{})
 rows=copy.deepcopy(base['records']);indexed={(r['organCode'],r['exp'],r['lot']):r for r in rows};dossiers={}
 for r in rows:
  scope=r.get('scope') or '';r['world']='generalitat' if 'Generalitat' in scope else 'local' if 'local' in scope else mapping.get(r['organCode'],{}).get('world','other');r['territory']='catalunya'
  doc=docs.get(r['id'],{});lot=next((l for l in doc.get('lots',[]) if str(l.get('lot') or '')==str(r['lot'])),{})
  dossiers[r['id']]={'singleLot':len(doc.get('lots',[]))==1,'terms':lot.get('terms',{}),'attachments':doc.get('attachments',[]),'sources':[r['source']],'structuredSource':doc.get('source'),'fetched':doc.get('fetched'),'sourceHash':doc.get('documentHash'),'recordHash':r['rawHash']}
  r['sdaParent']=None;r['isSystem']='sistema din' in norm(r.get('rationalization',''))
 for parent,board in boards['parents'].items():
  for notice in board['notices']:
   for inv in notice.get('invitations',[]):
    if inv.get('error'):continue
    for lot in inv.get('lots') or [{'lot':None}]:
     exp=inv['exp'];n=str(lot.get('lot') or '')
     found=indexed.get(('11110',exp,n))
     if found is None:
      matching=[r for r in rows if r['organCode']=='11110' and r['exp']==exp]
      if not n and len(matching)==1:found=matching[0]
     if found is None:
      found={'id':'board|'+parent+'|'+exp+'|'+n,'exp':exp,'organCode':'11110','organ':'Centre de Telecomunicacions i Tecnologies de la Informació de la Generalitat de Catalunya','scope':'Generalitat de Catalunya','world':'generalitat','territory':'catalunya','lot':n,'lotTitle':'','title':inv.get('title') or notice['title'],'description':inv.get('description') or notice['description'],'cpv':[lot['cpv']] if lot.get('cpv') else [],'tic':True,'phase':inv.get('phase'),'result':None,'procedure':'Contracte específic SDA','rationalization':'Contracte específic SDA','budget':lot.get('budget') or inv.get('budget'),'contractBudget':inv.get('budget'),'vec':inv.get('vec'),'awarded':lot.get('awarded'),'winner':'','offers':None,'deadline':inv.get('deadline'),'published':inv.get('published') or notice['dataPublicacio'],'awardDate':None,'duration':'','endDate':None,'discount':{'value':None,'reason':''},'source':inv['source'],'sourceQuery':notice['api'],'documents':{},'rawHash':notice.get('sourceHash') or hashlib.sha256(exp.encode()).hexdigest(),'candidates':[],'isSystem':False}
      rows.append(found);indexed[('11110',exp,n)]=found
     r=found;r['sdaParent']=parent;r['noticePublished']=notice['dataPublicacio'];r['categories']=[c['titolLot'] for c in notice.get('categories',[])];r['categoryIds']=[str(c['numeroLot']) for c in notice.get('categories',[])]
     current=inv.get('currentPublication')
     if current and (current.get('published') or '')>=(r.get('published') or ''):
      r['phase']=current.get('phase') or r['phase'];r['published']=current.get('published') or r['published'];r['source']=current['source']
      award=next((l for l in current.get('lots',[]) if str(l.get('lot') or '')==n),{})
      if award.get('awarded') is not None:r['awarded']=award['awarded']
      if award.get('winners'):r['winner']=' || '.join(award['winners'])
      r['discount']=discount(r.get('budget'),r.get('awarded'),multi=' || ' in r.get('winner',''))
     # Preserve newer dataset status; fill missing announcement facts only.
     r['deadline']=r.get('deadline') or inv.get('deadline');r['vec']=r.get('vec') or inv.get('vec')
     d=dossiers.setdefault(r['id'],{});d.update(singleLot=len(inv.get('lots',[]))==1,terms=lot.get('terms',{}),attachments=inv.get('attachments',[]),sources=list(dict.fromkeys([r['source'],notice['source'],inv['source']])),notice=notice.get('description'),fetched=boards['generated'],recordHash=r['rawHash'],sourceHash=notice.get('sourceHash'))
 for r in bal['records']:
  r=copy.deepcopy(r);r['world']='local';r['territory']='balears';r['isSystem']='sistema din' in norm(r.get('rationalization',''));r['sdaParent']=None
  dossiers[r['id']]={'terms':r.pop('terms',{}),'attachments':r.pop('attachments',[]),'sources':[r['source']],'fetched':bal.get('generated'),'recordHash':r['rawHash']};rows.append(r)
 sda=read('sda.json',{'parents':{}})
 byid={r['id']:r for r in rows}
 for parent,p in sda['parents'].items():
  for c in p.get('children',[]):
   if c['id'] in byid:byid[c['id']]['sdaParent']=parent
 candidates(rows)
 for r in rows:
  r['shortTitle']=short_title(r.get('lotTitle') or r['title']);r['category']=category(r['title']);r['key']=hashlib.sha256(r['id'].encode()).hexdigest()[:18]
  r.pop('documents',None);r.pop('sourceQuery',None);r.pop('documentsDeferred',None)
  r['description']=r['description'][:2200]
  if r['id'] in dossiers:dossiers[r['id']]['key']=r['key']
 result={'generated':dt.datetime.now(dt.timezone.utc).isoformat(),'sourcesUpdated':{'pscp':base['generated'],'sda':boards.get('generated'),'balears':bal.get('generated')},'records':rows,'changes':base.get('changes',[]),'boards':{k:{'total':v['total'],'source':v['source']} for k,v in boards['parents'].items()},'coverage':{'balearsSince':bal.get('since'),'balearsOrgans':bal.get('directoryCount'),'pscpSince':'2022-01-01'}}
 (D/'catalog.json.gz').write_bytes(gzip.compress(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
 (D/'dossiers.json').write_text(json.dumps(dossiers,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 print('Catàleg:',len(rows),'; SDA:',sum(bool(r['sdaParent']) for r in rows),'; Balears:',len(bal['records']),flush=True)
if __name__=='__main__':main()
