"""Taulers SDA: avisos públics, totes les pàgines i enllaços publicats pel tauler."""
import concurrent.futures,datetime as dt,hashlib,json,re,urllib.parse
from refresh import ROOT,get,number
from enrich import attachments
from terms import terms
PARENTS={'CTTI-2025-96':'43ced24f-d1ae-4950-88cb-51ac72424929','CTTI-2026-129':'f20be25b-2eef-42f5-ab76-2bd33b9bbb22'}
API='https://contractaciopublica.cat/portal-api'
def text(v):return (v.get('text') or v.get('ca') or '') if isinstance(v,dict) else str(v or '')

def invitation_summary(payload,source):
    d=payload.get('dades') or {};pub=d.get('publicacio') or {};basic=pub.get('dadesBasiquesPublicacio') or {};general=pub.get('dadesPublicacio') or {}
    return {'exp':payload.get('codiExpedient'),'title':payload.get('titol'), 'phase':text(pub.get('fase')),
        'published':d.get('dataPublicacioReal'),'deadline':general.get('dataTerminiPresentacioOSolicitud'),
        'budget':number(general.get('pressupostLicitacio')),'vec':number(general.get('valorEstimatContracte')),'description':text(basic.get('descripcio')),
        'exclusiveAccess':payload.get('accesExclusiu'),'source':source,'attachments':attachments(pub),
        'lots':[{'lot':lot.get('numeroLot'),'terms':terms(lot,general),'cpv':(lot.get('cpvPrincipal') or {}).get('codi'),'budget':number(lot.get('pressupostLicitacio')),'awarded':number(lot.get('importAdjudicacio')),
            'parent':lot.get('codiExpedientReferencia') or basic.get('codiExpedientReferencia'),'categoryReference':lot.get('numeroLotExpedientReferencia'),
            'criteria':[{'label':text(c.get('criteri')),'weight':c.get('ponderacio')} for c in lot.get('criterisAdjudicacio',[]) or []],
            'winners':[text(w.get('denominacio')) for w in lot.get('empresesAdjudicataries',[]) or []]} for lot in pub.get('dadesPublicacioLot',[]) or []]}

def detail(item):
    item=dict(item);item['source']=f"https://contractaciopublica.cat/ca/detall-avis/avis-recurs/{item['id']}"
    item['api']=f"{API}/detall-avis/avis-recurs/{item['id']}";item['invitations']=[]
    try:
        doc=get(item['api']);d=doc.get('dades') or {}
        item.update(title=d.get('titol') or item.get('titol'),description=d.get('descripcio') or item.get('descripcio'),
            categories=d.get('lots') or [],links=d.get('linkInteres') or [],detailStatus='checked',
            sourceHash=hashlib.sha256(json.dumps(doc,ensure_ascii=False,sort_keys=True).encode()).hexdigest())
        for link in item['links']:
            url=link.get('url') or '';parsed=urllib.parse.urlparse(url)
            m=re.search(r'/detall-publicacio/([a-f0-9-]{36})/(\d+)',parsed.path)
            if parsed.hostname!='contractaciopublica.cat' or not m:continue
            # Only use the token already published in this public board's own link.
            token=urllib.parse.parse_qs(parsed.query).get('hash',[''])[0]
            endpoint=f'{API}/detall-publicacio-expedient/{m[1]}/{m[2]}'
            if token:endpoint+='?'+urllib.parse.urlencode({'hash':token})
            try:
                payload=get(endpoint)
                invitation=invitation_summary(payload,url)
                navigation=(payload.get('navegacioFases') or [])+(payload.get('navegacioEsmenes') or [])
                latest=max(navigation,key=lambda x:x.get('dataPublicacio') or '',default={})
                pid=latest.get('publicacioId')
                if pid and str(pid)!=m[2]:
                    latest_endpoint=f'{API}/detall-publicacio-expedient/{m[1]}/{pid}'
                    if token:latest_endpoint+='?'+urllib.parse.urlencode({'hash':token})
                    try:
                        current=invitation_summary(get(latest_endpoint),f'https://contractaciopublica.cat/ca/detall-publicacio/{m[1]}/{pid}'+('?'+urllib.parse.urlencode({'hash':token}) if token else ''))
                        if current['exp']==invitation['exp']:
                            if current['phase']=='Anunci de licitació':invitation=current
                            else:
                                invitation['currentPublication']=current
                                invitation['phase']=current['phase'];invitation['published']=current['published']
                                invitation['deadline']=current.get('deadline') or invitation.get('deadline')
                    except Exception as error:invitation['latestError']=type(error).__name__
                item['invitations'].append(invitation)
            except Exception as error:item['invitations'].append({'source':url,'error':'No disponible: '+str(error)[:120]})
    except Exception as error:item.update(title=item.get('titol'),description=item.get('descripcio'),detailStatus='error',error=str(error)[:150],categories=[],links=[])
    exps=re.findall(r'CTTI\s*[-–]?\s*(20\d\d)\s*[-–]\s*(\d+)',item.get('title') or '',re.I)
    item['contracts']=list(dict.fromkeys('CTTI-'+y+'-'+n for y,n in exps))
    item['kind']='Avís de contracte específic' if any(x!=item['parent'] for x in item['contracts']) else 'Altre avís del tauler'
    return item

def main():
    path=ROOT/'site/data';result={'generated':dt.datetime.now(dt.timezone.utc).isoformat(),'parents':{},'method':'API pública del tauler, categoria 1008354. Paginació fins al total declarat; lectura dels detalls i dels enllaços que publica cada avís.'}
    for parent,uuid in PARENTS.items():
        page=0;items=[];expected=None;pages=[]
        while True:
            endpoint=f'{API}/avisos-tauler/1008354/{uuid}?page={page}&size=20';response=get(endpoint)
            if 'content' not in response or 'totalElements' not in response:raise ValueError('Format del tauler desconegut; no es publica')
            if expected is None:expected=response['totalElements']
            items+=response['content'];pages.append(endpoint)
            if response.get('last') or page+1>=response['totalPages']:break
            page+=1
            if page>100:raise ValueError('Paginació del tauler supera el límit; no es publica parcialment')
        unique={str(x['id']):x for x in items}
        if len(unique)!=expected:raise ValueError('El tauler ha canviat durant la consulta; torna a executar')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            notices=list(pool.map(detail,[x|{'parent':parent} for x in unique.values()]))
        result['parents'][parent]={'source':f'https://contractaciopublica.cat/ca/tauler-avisos/empreses-admeses-sistema/{uuid}?page=0',
            'total':expected,'pages':pages,'complete':True,'notices':notices,'detailErrors':sum(x['detailStatus']=='error' for x in notices)}
        print(parent,'avisos',len(notices),'expedients',len({c for x in notices for c in x['contracts'] if c!=parent}),flush=True)
    (path/'boards.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
if __name__=='__main__':main()
