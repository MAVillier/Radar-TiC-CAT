"""Importació PSCP reproduïble. Python 3.11+, només biblioteca estàndard."""
import argparse, collections, datetime as dt, decimal, gzip, hashlib, json, pathlib, re, time, unicodedata
import urllib.parse, urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = 'https://analisi.transparenciacatalunya.cat/resource/ybgg-dgi6.json'
META = 'https://analisi.transparenciacatalunya.cat/api/views/ybgg-dgi6.json'
FIELDS = ('id_intern,codi_organ,nom_organ,nom_ambit,codi_expedient,numero_lot,descripcio_lot,'
          'denominacio,objecte_contracte,codi_cpv,fase_publicacio,resultat,procediment,'
          'racionalitzacio_contractacio,pressupost_licitacio_sense,pressupost_licitacio_sense_1,'
          'valor_estimat_contracte,import_adjudicacio_sense,denominacio_adjudicatari,'
          'ofertes_rebudes,termini_presentacio_ofertes,durada_contracte,data_adjudicacio_contracte,'
          'data_publicacio_anunci,data_publicacio_adjudicacio,data_publicacio_formalitzacio,'
          'data_publicacio_previ,data_publicacio_futura,data_publicacio_avaluacio,data_publicacio_anul,'
          'enllac_publicacio,url_json_licitacio,url_json_avaluacio,url_json_adjudicacio,url_json_formalitzacio')
DATE_FIELDS = [x for x in FIELDS.split(',') if x.startswith('data_publicacio_')]
PREFIXES = ['302','48','72','322','324','325','642','5031','5032','5131','5161','3012']

def get(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'RadarTIC/2.0 (public procurement research)','Accept':'application/json'})
            with urllib.request.urlopen(req, timeout=90) as res:
                return json.load(res)
        except Exception:
            if attempt == 3: raise
            time.sleep(2 ** attempt)

def query(**params):
    return API + '?' + urllib.parse.urlencode({'$'+k:v for k,v in params.items()})

def number(value):
    # Reject multi-award concatenations, ambiguous locale formats and non-finite values.
    if value is None or not re.fullmatch(r'-?\d+(?:\.\d+)?', str(value).strip()): return None
    n = decimal.Decimal(str(value).strip())
    return float(n) if n.is_finite() else None

def discount(base, awarded, aggregate=False, multi=False):
    b, a = number(base), number(awarded)
    if aggregate or multi: return {'value':None,'reason':'Imports agregats o diversos adjudicataris: cal revisar el document.'}
    if b is None or a is None or b <= 0 or a < 0: return {'value':None,'reason':'Falten imports homogenis vàlids sense IVA.'}
    if a > b: return {'value':None,'reason':'Adjudicació superior al pressupost: cal revisar període, lots i unitats.'}
    value = (decimal.Decimal(str(b))-decimal.Decimal(str(a)))/decimal.Decimal(str(b))*100
    return {'value':float(value.quantize(decimal.Decimal('.01'))),'reason':'Diferència calculada entre imports del mateix registre i lot, sense IVA. No acredita la baixa ofertada sobre preus unitaris ni una revisió dels plecs.'}

def url(value):
    value = value.get('url','') if isinstance(value,dict) else value or ''
    return value if urllib.parse.urlparse(value).scheme == 'https' else ''

def stamp(row): return max((row.get(k) or '' for k in DATE_FIELDS), default='')
def identity(r): return '|'.join(str(r.get(k) or '') for k in ('codi_organ','id_intern','codi_expedient','numero_lot'))

def normalize(r):
    cpv = [x.strip() for x in (r.get('codi_cpv') or '').split('||') if x.strip()]
    winner = r.get('denominacio_adjudicatari') or ''
    k = identity(r)
    source_query = query(where="id_intern='" + (r.get('id_intern') or '').replace("'","''") + "'",limit=5000)
    end = re.search(r'\d{2}/\d{2}/\d{4}\s+a\s+(\d{2}/\d{2}/\d{4})', r.get('durada_contracte') or '')
    end_date = None
    if end:
        try: end_date = dt.datetime.strptime(end[1],'%d/%m/%Y').date().isoformat()
        except ValueError: pass
    return dict(id=k,exp=r.get('codi_expedient'),organCode=r.get('codi_organ'),organ=r.get('nom_organ'),
        scope=r.get('nom_ambit'),lot=r.get('numero_lot') or '',lotTitle=r.get('descripcio_lot') or '',
        title=r.get('denominacio') or r.get('objecte_contracte') or '',description=r.get('objecte_contracte') or '',
        cpv=cpv,tic=any(c.startswith(tuple(PREFIXES)) for c in cpv),phase=r.get('fase_publicacio'),result=r.get('resultat'),
        procedure=r.get('procediment') or '',rationalization=r.get('racionalitzacio_contractacio') or '',
        budget=number(r.get('pressupost_licitacio_sense')),contractBudget=number(r.get('pressupost_licitacio_sense_1')),
        vec=number(r.get('valor_estimat_contracte')),awarded=number(r.get('import_adjudicacio_sense')),winner=winner,
        offers=number(r.get('ofertes_rebudes')),deadline=r.get('termini_presentacio_ofertes'),published=stamp(r),
        awardDate=r.get('data_adjudicacio_contracte') or r.get('data_publicacio_adjudicacio'),
        duration=r.get('durada_contracte') or '',endDate=end_date,
        discount=discount(r.get('pressupost_licitacio_sense'),r.get('import_adjudicacio_sense'),
            r.get('fase_publicacio')=='Publicació agregada de contractes','||' in winner),
        source=url(r.get('enllac_publicacio')),sourceQuery=source_query,
        documents={key.removeprefix('url_json_'):url(r.get(key)) for key in FIELDS.split(',') if key.startswith('url_json_') and r.get(key)},
        rawHash=hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False).encode()).hexdigest())

STOP = set('de del dels la les el els un una i en per al als amb contracte serveis servei subministrament objecte present contractacio construccio desenvolupament manteniment gestio sistema sistemes informacio generalitat catalunya'.split())
def words(s):
    s = ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c) != 'Mn')
    return set(re.findall(r'[a-z0-9]{3,}', s))-STOP

def candidates(rows):
    groups=collections.defaultdict(list)
    for r in rows:
        if r['winner'] and r['awardDate'] and r['phase'] in ('Adjudicació','Formalització'): groups[r['organCode']].append(r)
    for r in rows:
        r['candidates']=[]
        if r['phase'] not in ('Anunci de licitació','Expedient en avaluació','Anunci previ','Publicació de futura licitació'): continue
        rw=words(r['title']+' '+r['description'])
        for old in groups[r['organCode']]:
            if old['exp']==r['exp'] or old['awardDate'] >= (r['published'] or ''): continue
            common=set(r['cpv']) & set(old['cpv'])
            ow=words(old['title']+' '+old['description'])
            overlap=rw & ow
            score=len(overlap)/max(1,len(rw|ow))
            if common and len(overlap)>=3 and score>=.15:
                r['candidates'].append({'id':old['id'],'score':round(score,3),'terms':sorted(overlap)[:12], 'cpv':sorted(common)})
        r['candidates']=sorted(r['candidates'],key=lambda x:x['score'],reverse=True)[:5]

def build(raw, meta, where, started, fetched):
    latest={}
    for r in raw:
        key=identity(r)
        if key not in latest or (stamp(r),url(r.get('enllac_publicacio'))) > (stamp(latest[key]),url(latest[key].get('enllac_publicacio'))): latest[key]=r
    rows=[normalize(r) for r in latest.values()]
    candidates(rows)
    return {'generated':fetched,'started':started,'source':API,'sourceUpdated':meta.get('rowsUpdatedAt'),
        'coverage':{'since':'2022-01-01','where':where,'rawCount':len(raw),'records':len(rows),'completePagination':True,
        'note':'Publicacions amb data des de 2022, CPV TIC configurats i tot el CTTI. No inclou contractes antics sense cap publicació recent, ni permet assegurar cobertura universal. La font pot actualitzar-se durant la descàrrega.'},
        'records':rows}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--raw-file'); args=parser.parse_args()
    started=dt.datetime.now(dt.timezone.utc).isoformat()
    recent='('+' OR '.join(k+">='2022-01-01T00:00:00'" for k in DATE_FIELDS)+')'
    tic='('+' OR '.join("codi_cpv like '"+p+"%' OR codi_cpv like '%||"+p+"%' OR codi_cpv like '%|| "+p+"%'" for p in PREFIXES)+" OR codi_organ='11110')"
    where=recent+' AND '+tic
    if args.raw_file:
        raw=json.loads(pathlib.Path(args.raw_file).read_text(encoding='utf-8')); meta={}
    else:
        meta=get(META); raw=[]; offset=0
        while True:
            page=get(query(select=FIELDS,where=where,order='id_intern,numero_lot,codi_organ,codi_expedient',limit=5000,offset=offset))
            if not isinstance(page,list): raise ValueError('Resposta inesperada; no es publica.')
            raw.extend(page); print('Registres rebuts:',len(raw),flush=True)
            if len(page)<5000: break
            offset+=5000
            if offset>=250000: raise RuntimeError('Límit de seguretat assolit: no es publica una extracció truncada.')
        if not raw: raise ValueError('Extracció buida: revisa la font abans de publicar.')
    fetched=dt.datetime.now(dt.timezone.utc).isoformat()
    data=build(raw,meta,where,started,fetched)
    target=ROOT/'site'/'data'; target.mkdir(parents=True,exist_ok=True)
    previous=target/'radar.json'
    packed=target/'radar.json.gz'
    old=json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else (json.loads(gzip.decompress(packed.read_bytes())) if packed.exists() else None)
    old_map={r['id']:r for r in old['records']} if old else {}
    data['changes']=[{'id':r['id'],'kind':'Nou' if r['id'] not in old_map else 'Actualitzat'} for r in data['records'] if old_map and (r['id'] not in old_map or r['rawHash']!=old_map[r['id']]['rawHash'])]
    data['baselineAvailable']=bool(old_map)
    temp=target/'radar.tmp'; temp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8'); temp.replace(previous)
    # Raw source evidence is shipped with the data, with no authentication tokens.
    (target/'raw.json').write_text(json.dumps(raw,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (target/'provenance.json').write_text(json.dumps({'fetched':fetched,'query':query(select=FIELDS,where=where),'metadata':META,'sourceUpdated':meta.get('rowsUpdatedAt'),'rawCount':len(raw)},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'records':len(data['records']),'candidates':sum(bool(r['candidates']) for r in data['records'])}))

if __name__=='__main__': main()
