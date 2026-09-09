"""Govern Balear and instrumental entities: PLACSP annual backfill and incremental ATOM."""
import argparse,datetime as dt,hashlib,io,json,pathlib,re,time,urllib.request,zipfile,xml.etree.ElementTree as E,shutil,subprocess
from refresh import ROOT,PREFIXES,discount,candidates
FEED='https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom'
DIRECTORY='https://contrataciondelsectorpublico.gob.es/datosabiertos/OrganosContratacion.xlsx'
NS={'a':'http://www.w3.org/2005/Atom','b':'urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2','c':'urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2','e':'urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2','x':'urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2'}
TOMBSTONES={}
VERSIONS={}
def fetch(url):
    # The platform intermittently resets Python TLS connections. curl keeps
    # certificate verification enabled and is available on Actions and Windows.
    executable=shutil.which('curl.exe') or shutil.which('curl')
    if executable:return subprocess.run([executable,'--fail','--silent','--show-error','--location','--compressed','--max-time','90','--retry','2',url],capture_output=True,check=True,timeout=290).stdout
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RadarTIC/3.0 public procurement'}),timeout=45) as r:return r.read()
        except Exception:
            if attempt==3:raise
            time.sleep(2*(attempt+1))
def t(el,path,default=''):
    if el is None:return default
    return el.findtext(path,default,NS) or default
def num(el,path):
    try:return float(t(el,path))
    except ValueError:return None
def profiles(raw):
    import openpyxl
    w=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    return {str(r[0]):{'name':r[1],'parent':r[3],'hierarchy':r[4],'nif':r[5]} for r in w.active.iter_rows(values_only=True)
            if len(r)>5 and (r[3]=='Comunidad Autónoma Illes Balears' or r[3]=='SOCIEDADES, FUNDACIONES Y CONSORCIOS COMUNIDADES AUTÓNOMAS' and str(r[4]).startswith('Illes Balears>'))}
def parse_entry(entry,orgs):
    status=entry.find('e:ContractFolderStatus',NS)
    if status is None:return []
    party=status.find('e:LocatedContractingParty/c:Party',NS)
    code=t(party,"c:PartyIdentification/b:ID[@schemeName='ID_PLATAFORMA']")
    if code not in orgs:return []
    project=status.find('c:ProcurementProject',NS)
    cpvs=[x.text for x in status.findall('c:ProcurementProject/c:RequiredCommodityClassification/b:ItemClassificationCode',NS) if x.text]
    lots=status.findall('c:ProcurementProjectLot',NS)
    for lot in lots:cpvs.extend(x.text for x in lot.findall('c:ProcurementProject/c:RequiredCommodityClassification/b:ItemClassificationCode',NS) if x.text)
    if not any(c.startswith(tuple(PREFIXES)) for c in cpvs):return []
    idbase=t(entry,'a:id').rsplit('/',1)[-1];exp=t(status,'b:ContractFolderID');phasecode=t(status,'x:ContractFolderStatusCode')
    phase={'PUB':'Anunci de licitació','EV':'Expedient en avaluació','ADJ':'Adjudicació','RES':'Formalització','ANUL':'Anul·lació','PRE':'Anunci previ'}.get(phasecode,phasecode)
    link=entry.find('a:link',NS);source=link.get('href','') if link is not None else ''
    end=t(status,'c:TenderingProcess/c:TenderSubmissionDeadlinePeriod/b:EndDate');hour=t(status,'c:TenderingProcess/c:TenderSubmissionDeadlinePeriod/b:EndTime')
    deadline=end+'T'+hour if end and hour else None
    cr=[]
    for c in status.findall('c:TenderingTerms/c:AwardingTerms/c:AwardingCriteria',NS):
        cr.append({'label':t(c,'b:Description'),'weight':num(c,'b:WeightNumeric'),'kind':'technical' if t(c,'b:AwardingCriteriaTypeCode')=='SUBJ' else 'automatic','children':[]})
    attachments=[]
    for tag in ('LegalDocumentReference','TechnicalDocumentReference','AdditionalDocumentReference'):
        for doc in status.findall('c:'+tag,NS):
            u=t(doc,'c:Attachment/c:ExternalReference/b:URI')
            if u.startswith('https:'):attachments.append({'title':t(doc,'b:ID') or tag,'url':u})
    results=status.findall('c:TenderResult',NS);out=[]
    for lot in lots or [None]:
        n=t(lot,'b:ID') if lot is not None else '';p=lot.find('c:ProcurementProject',NS) if lot is not None else project
        lotcpv=[x.text for x in p.findall('c:RequiredCommodityClassification/b:ItemClassificationCode',NS) if x.text] if p is not None else []
        if lotcpv and not any(c.startswith(tuple(PREFIXES)) for c in lotcpv):continue
        matched=[r for r in results if t(r,'c:AwardedTenderedProject/b:ProcurementProjectLotID')==n]
        # Do not assign an unallocated contract-level award to every lot.
        winner=' || '.join(dict.fromkeys(t(r,'c:WinningParty/c:PartyName/b:Name') for r in matched if t(r,'c:WinningParty/c:PartyName/b:Name')))
        amounts=[num(r,'c:AwardedTenderedProject/c:LegalMonetaryTotal/b:TaxExclusiveAmount') for r in matched];awarded=amounts[0] if len(amounts)==1 else None
        budget=num(p,'c:BudgetAmount/b:TaxExclusiveAmount');dur=p.find('c:PlannedPeriod/b:DurationMeasure',NS) if p is not None else None
        duration=((dur.text or '')+' '+{'MON':'mesos','ANN':'anys','DAY':'dies'}.get(dur.get('unitCode'),'unitats')) if dur is not None else ''
        v=num(p,'c:BudgetAmount/b:EstimatedOverallContractAmount')
        row={'id':'placsp|'+code+'|'+idbase+'|'+n,'exp':exp,'organCode':'placsp:'+code,'organ':orgs[code]['name'],'scope':'Govern de les Illes Balears','world':'local','territory':'balears','lot':n,'lotTitle':t(p,'b:Name') if lot is not None else '',
        'title':t(entry,'a:title'),'description':t(project,'b:Name'),'cpv':lotcpv or cpvs,'tic':True,'phase':phase,'result':phasecode,'procedure':t(status,'c:TenderingProcess/b:ProcedureCode'),'rationalization':'Sistema dinàmic d’adquisició' if t(status,'c:TenderingProcess/b:ContractingSystemCode')=='2' else '',
        'budget':budget,'contractBudget':num(project,'c:BudgetAmount/b:TaxExclusiveAmount'),'vec':v,'awarded':awarded,'winner':winner,'offers':num(matched[0],'b:ReceivedTenderQuantity') if len(matched)==1 else None,'deadline':deadline,'published':t(entry,'a:updated'),'awardDate':t(matched[0],'b:AwardDate') if matched else None,'duration':duration,'endDate':t(p,'c:PlannedPeriod/b:EndDate') or None,
        'discount':discount(budget,awarded,multi=len(matched)>1),'source':source,'sourceQuery':FEED,'documents':{},'rawHash':hashlib.sha256(E.tostring(entry)).hexdigest(),'candidates':[],
        'terms':{'duration':duration,'vec':v,'criteria':cr,'extensionText':t(p,'c:ContractExtension/b:OptionsDescription'),'extensionAllowed':True if p is not None and p.find('c:ContractExtension',NS) is not None else None},'attachments':attachments}
        if phasecode=='RES':row['phase']='Adjudicació' if winner else 'Resolt'
        out.append(row)
    return out
def consume(raw,orgs,state):
    header=re.search(rb'<feed\b[^>]*>',raw)
    if not header:raise ValueError('Missing ATOM feed')
    dates=[];count=0
    for block in re.findall(rb'<entry\b.*?</entry>',raw,re.S):
        updated=re.search(rb'<updated>(.*?)</updated>',block)
        if updated:dates.append(updated[1].decode())
        oid=re.search(rb'<cbc:ID\s+schemeName="ID_PLATAFORMA">(\d+)</cbc:ID>',block)
        if not oid or oid[1].decode() not in orgs:continue
        entry=E.fromstring(header[0]+block+b'</feed>').find('a:entry',NS)
        entry_id=t(entry,'a:id').rsplit('/',1)[-1];stamp=t(entry,'a:updated')
        if stamp<=max(TOMBSTONES.get(entry_id,''),VERSIONS.get(entry_id,'')):continue
        VERSIONS[entry_id]=stamp
        for key in list(state):
            if key.split('|')[2]==entry_id:del state[key]
        for r in parse_entry(entry,orgs):
            if r['id'] not in state or r['published']>state[r['id']]['published']:state[r['id']]=r
            count+=1
    # A tombstone means the record was withdrawn from the feed; remove all its lots.
    for tombstone in re.findall(rb'<at:deleted-entry\b[^>]*>',raw):
        ref=re.search(rb'ref="([^"]+)"',tombstone);when=re.search(rb'when="([^"]+)"',tombstone)
        if not ref or not when:continue
        suffix=ref[1].decode().rsplit('/',1)[-1];stamp=when[1].decode()
        TOMBSTONES[suffix]=max(TOMBSTONES.get(suffix,''),stamp)
        for k in list(state):
            if k.split('|')[2]==suffix and state[k]['published']<=stamp:del state[k]
    nextlinks=re.findall(rb'<link\b[^>]*rel="next"[^>]*href="([^"]+)"',raw[:5000])
    if not nextlinks:nextlinks=re.findall(rb'<link\b[^>]*href="([^"]+)"[^>]*rel="next"',raw[:5000])
    return min(dates,default=''),max(dates,default=''),nextlinks[0].decode().replace('&amp;','&') if nextlinks else None,count
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--archive',action='append',default=[]);ap.add_argument('--directory');args=ap.parse_args()
    target=ROOT/'site/data/balears.json';old=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    orgs=profiles(pathlib.Path(args.directory).read_bytes() if args.directory else fetch(DIRECTORY))
    if len(orgs)<20:raise ValueError('Unexpected official directory; aborting')
    state={r['id']:r for r in old.get('records',[])};watermark=old.get('watermark','');sources=list(old.get('archives',[]));pages=0;latest=watermark
    TOMBSTONES.update(old.get('tombstones',{}));VERSIONS.update(old.get('versions',{}))
    for row in state.values():
        key=row['id'].split('|')[2];VERSIONS[key]=max(VERSIONS.get(key,''),row['published'])
    state={k:r for k,r in state.items() if r['published']==VERSIONS[k.split('|')[2]]}
    def checkpoint(complete):
        rows=list(state.values());candidates(rows)
        result={'generated':dt.datetime.now(dt.timezone.utc).isoformat(),'watermark':latest,'archives':sources,'incrementalPages':pages,'directorySource':DIRECTORY,'directoryCount':len(orgs),'source':FEED,'records':rows,'since':'2025-01-01' if any('2025' in s for s in sources) else '2026-01-01','complete':complete}
        result.update(tombstones=TOMBSTONES,versions=VERSIONS)
        temp=target.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8');temp.replace(target)
    for archive in args.archive:
        if pathlib.Path(archive).name in sources:continue
        with zipfile.ZipFile(archive) as z:
            names=[n for n in z.namelist() if n.endswith('.atom')]
            for i,n in enumerate(names):
                low,high,_,_=consume(z.read(n),orgs,state);latest=max(latest,high)
                if i%100==0:print(pathlib.Path(archive).name,i,'/',len(names),'TIC',len(state),flush=True)
        if pathlib.Path(archive).name not in sources:sources.append(pathlib.Path(archive).name)
        checkpoint(False)
    if not state and not args.archive:raise RuntimeError('Cal una importació inicial amb --archive abans de fer actualitzacions incrementals')
    nexturl=FEED;seen=set();cutoff=watermark or latest
    while nexturl:
        if nexturl in seen or len(seen)>300:raise RuntimeError('Paginació PLACSP incompleta')
        seen.add(nexturl);low,high,nexturl,_=consume(fetch(nexturl),orgs,state);pages+=1;latest=max(latest,high)
        print('PLACSP pàgina',pages,'fins',low,'TIC',len(state),flush=True)
        if low and cutoff and low<cutoff:break
    checkpoint(True)
    print('Balears:',len(state),'lots / registres;',len(orgs),'òrgans;',pages,'pàgines incrementals',flush=True)
if __name__=='__main__':main()
