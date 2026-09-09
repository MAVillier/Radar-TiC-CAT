"""Relacions documentals SDA -> contracte específic. No són relacions d'incumbència."""
import concurrent.futures,datetime as dt,json,collections
from refresh import ROOT,get
from enrich import attachments
PARENTS=('CTTI-2025-96','CTTI-2026-129')

def parent_reference(pub,lot):
    for obj,path in ((lot,'publicacio.dadesPublicacioLot'),(pub.get('dadesBasiquesPublicacio',{}),'publicacio.dadesBasiquesPublicacio'),(pub.get('dadesExpedient',{}),'publicacio.dadesExpedient')):
        if obj.get('codiExpedientReferencia') in PARENTS:return obj['codiExpedientReferencia'],path+'.codiExpedientReferencia'
    return None,None

def inspect(r):
    docs=r['documents']; kind=next((k for k in ('formalitzacio','adjudicacio','avaluacio','licitacio') if docs.get(k)),None)
    result={'schemaVersion':2,'recordHash':r['rawHash'],'checked':dt.datetime.now(dt.timezone.utc).isoformat(),'links':[],'status':'no_document'}
    if not kind:return r['id'],result
    result['source']=docs[kind]
    try:
        doc=get(docs[kind]); assert doc.get('codiExpedient')==r['exp']
        pub=doc.get('publicacio',{});basic=pub.get('dadesBasiquesPublicacio',{})
        result['exclusiveAccess']=basic.get('accesExclusiu');result['attachments']=attachments(pub)
        for lot in pub.get('dadesPublicacioLot',[]) or []:
            parent,source_field=parent_reference(pub,lot)
            if parent not in PARENTS:continue
            # Only associate a lot with its matching document lot, except no-lot documents.
            if pub.get('teLots') is True and str(lot.get('numeroLot',''))!=r['lot']:continue
            result['links'].append({'parent':parent,'source':docs[kind],
                'sourceField':source_field,
                'referenceLotRaw':lot.get('numeroLotExpedientReferencia'),
                'invitedCompaniesCount':lot.get('numeroEmpresesConvidades'),
                'description':lot.get('descripcioLicitacio'),
                'note':'La numeració de referència es conserva literal; no es converteix automàticament en categoria.'})
        result['status']='checked'
    except Exception as e:result['status']='error';result['error']=str(e)[:150]
    return r['id'],result

def main():
    path=ROOT/'site/data';radar=json.loads((path/'radar.json').read_text(encoding='utf-8'))
    target=path/'sda.json';old=json.loads(target.read_text(encoding='utf-8')).get('inspections',{}) if target.exists() else {}
    # Scan every recent CTTI record, not just records whose rationalisation label is filled.
    rows=[r for r in radar['records'] if r['organCode']=='11110' and ((r['published'] or '')>='2025-01-01' or r['exp'] in PARENTS)]
    cache={r['id']:old[r['id']] for r in rows if r['id'] in old and old[r['id']].get('schemaVersion')==2 and old[r['id']].get('recordHash')==r['rawHash'] and old[r['id']].get('status')=='checked'}
    todo=[r for r in rows if r['id'] not in cache]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for k,v in pool.map(inspect,todo):cache[k]=v
    parents={}
    for code in PARENTS:
        parentRows=[r for r in rows if r['exp']==code]
        children=[{'id':r['id'],'exp':r['exp'],'phase':r['phase'],**link} for r in rows for link in cache[r['id']]['links'] if link['parent']==code and r['exp']!=code]
        parents[code]={'parentIds':[r['id'] for r in parentRows],'children':children,'uniqueContracts':len({r['exp'] for r in children})}
    result={'generated':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'Tots els registres CTTI amb publicació des de 2025 dins l’extracció principal. Relació exacta al JSON oficial, no semblança de títol.',
        'inspected':len(rows),'checked':sum(v['status']=='checked' for v in cache.values()),'errors':sum(v['status']=='error' for v in cache.values()),'noDocument':sum(v['status']=='no_document' for v in cache.values()),
        'visibilityWarning':'Les invitacions poden ser d’accés exclusiu per a empreses admeses. Cap resultat públic no acredita absència d’invitacions. Aquest radar no accedeix a la bústia privada de cap empresa.',
        'parents':parents,'inspections':cache}
    target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('inspections','parents')},ensure_ascii=False))
    print({k:v['uniqueContracts'] for k,v in parents.items()})
if __name__=='__main__':main()
