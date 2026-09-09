"""Comprimeix la instantània perquè la web no descarregui desenes de MB de text."""
import gzip,pathlib,json,collections
ROOT=pathlib.Path(__file__).resolve().parents[1]
source=ROOT/'site/data/radar.json'
if source.exists():
    data=json.loads(source.read_text(encoding='utf-8'))
    buckets=collections.defaultdict(dict)
    for r in data['records']:
        buckets[r['rawHash'][0]][r['id']]=r['documents']
        r['documents']={}
        r['documentsDeferred']=True
    for prefix,entries in buckets.items():
        (source.parent/f'documents-{prefix}.json.gz').write_bytes(gzip.compress(json.dumps(entries,ensure_ascii=False,separators=(',',':')).encode(),compresslevel=9,mtime=0))
    source.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
for name in ('radar.json','raw.json'):
    p=ROOT/'site/data'/name
    if p.exists():
        target=p.with_suffix(p.suffix+'.gz')
        target.write_bytes(gzip.compress(p.read_bytes(),compresslevel=9,mtime=0))
        print(target.name,target.stat().st_size)
        p.unlink()
