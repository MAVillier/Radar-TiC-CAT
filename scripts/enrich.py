"""Lectura limitada de JSON oficials. Conserva lots, fonts i camps sense inferir guanyadors."""
import concurrent.futures, datetime as dt, hashlib, json, os, pathlib
from refresh import ROOT, get, number
from terms import terms

def text(v):
    if isinstance(v,dict): return v.get('text') or v.get('ca') or v.get('es') or ''
    return str(v or '')

def attachments(value):
    out=[]
    def walk(v):
        if isinstance(v,dict):
            if v.get('id') and v.get('hash') and str(v.get('titol','')).lower().endswith('.pdf'):
                out.append({'title':v['titol'],'url':'https://contractaciopublica.cat/portal-api/descarrega-document/'+str(v['id'])+'/'+v['hash']})
            for child in v.values():walk(child)
        elif isinstance(v,list):
            for child in v:walk(child)
    walk(value)
    return list({x['url']:x for x in out}.values())

def extract(doc):
    publication=doc.get('publicacio',{})
    lots=[]
    for lot in publication.get('dadesPublicacioLot',[]) or []:
        # A missing number is only safe for a document explicitly declaring no lots.
        n=lot.get('numeroLot')
        if n is None and publication.get('teLots') is True: continue
        n='' if publication.get('teLots') is False else str(n or '')
        lots.append({'lot':str(n),'terms':terms(lot,publication.get('dadesPublicacio')),'criteria':[{'label':text(c.get('criteri')),'weight':c.get('ponderacio')} for c in lot.get('criterisAdjudicacio',[]) or []],
            'companies':[text(c.get('empresa')) for c in lot.get('identitatEmpresa',[]) or []],
            'winners':[text(c.get('denominacio')) for c in lot.get('empresesAdjudicataries',[]) or []],
            'budget':number(lot.get('pressupostLicitacio')),'awarded':number(lot.get('importAdjudicacio')),
            'unitPrices':lot.get('preuUnitari'),'referenceContract':lot.get('codiExpedientReferencia'),
            'referenceWarning':'Una referència a un acord marc o SDA no identifica el contracte predecessor.',
            'sourcePath':'publicacio.dadesPublicacioLot','observations':text(lot.get('observacions'))})
    return lots

def process(r):
    docs=r['documents']; kind=next((k for k in ('licitacio','formalitzacio','adjudicacio','avaluacio') if docs.get(k)),None)
    if not kind:return r['id'],None
    fetched=dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        doc=get(docs[kind]); actual=doc.get('codiExpedient')
        if actual != r['exp']: raise ValueError('Expedient del document diferent del registre')
        lots=extract(doc)
        return r['id'],{'schemaVersion':3,'fetched':fetched,'source':docs[kind],'recordHash':r['rawHash'],'status':'Document oficial llegit',
            'documentHash':hashlib.sha256(json.dumps(doc,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'lots':lots,'attachments':attachments(doc.get('publicacio',{}))}
    except Exception as e:return r['id'],{'fetched':fetched,'recordHash':r['rawHash'],'status':'No s’ha pogut extreure el document: '+str(e)[:120],'lots':[]}

def main():
    path=ROOT/'site/data'; radar=json.loads((path/'radar.json').read_text(encoding='utf-8'))
    target=path/'documents.json'; old=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    now=dt.datetime.now().isoformat(); rows=radar['records']
    priority=lambda r:(0 if r['phase']=='Anunci de licitació' and (r['deadline'] or '')>now else 1,0 if r['organCode']=='11110' else 1, -(int((r['published'] or '2000')[:4])))
    rows=sorted(rows,key=lambda r:r['published'] or '',reverse=True); rows.sort(key=priority)
    current={r['id']:r for r in radar['records']}
    # Discard stale enrichment whenever the source record changed.
    out={k:v for k,v in old.items() if k in current and v.get('recordHash')==current[k]['rawHash']}
    todo=[r for r in rows if r['id'] not in out or not out[r['id']].get('lots') or out[r['id']].get('schemaVersion')!=3][:int(os.environ.get('DOCUMENT_LIMIT','240'))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for k,v in pool.map(process,todo):
            if v:out[k]=v
    target.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('Documents',len(out),'amb lots',sum(bool(v.get('lots')) for v in out.values()))

if __name__=='__main__':main()
