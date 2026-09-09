import json, pathlib, sys, gzip
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/'site/data/radar.json'
d=json.loads(p.read_text(encoding='utf-8') if p.exists() else gzip.decompress(p.with_suffix('.json.gz').read_bytes()))
assert d['coverage']['completePagination'] is True
assert d['records'], 'No es publica una extracció buida'
assert len({r['id'] for r in d['records']})==len(d['records']), 'Identificadors duplicats'
ids={r['id'] for r in d['records']}
for r in d['records']:
    assert r['source'].startswith('https://contractaciopublica.'), 'Font inesperada'
    assert r['discount']['value'] is None or 0<=r['discount']['value']<=100
    assert all(c['id'] in ids and c['id']!=r['id'] for c in r['candidates'])
for f in ('index.html','style.css','app.js','metodologia.html','data/evidence.json','data/documents.json'):
    assert (ROOT/'site'/f).exists(),f
print('Publicació vàlida:',len(ids),'registres')

b=json.loads((ROOT/'site/data/boards.json').read_text(encoding='utf-8'))
for code in ('CTTI-2025-96','CTTI-2026-129'):
    p=b['parents'][code]
    assert p['complete'] and len({n['id'] for n in p['notices']})==p['total']
    assert all(n['parent']==code and n['source'].startswith('https://contractaciopublica.cat/') for n in p['notices'])
print('Taulers complets:',{k:v['total'] for k,v in b['parents'].items()})

import gzip
c=json.loads(gzip.decompress((ROOT/'site/data/catalog.json.gz').read_bytes()))
rows=c['records'];keys={r['key'] for r in rows};assert len(keys)==len(rows)
bal=json.loads((ROOT/'site/data/balears.json').read_text(encoding='utf-8'))
assert bal['complete'] and bal['records'] and bal['directoryCount']>=20
assert all(r['world']=='local' and r['territory']=='balears' for r in rows if r['id'].startswith('placsp|'))
assert sum(r['id'].startswith('placsp|') for r in rows)==len(bal['records'])
for name in ('workspace.js','workspace-pdf.js','core.js','workspace.css','vendor/pdf-lib.min.js','updates.xml','data/news.json','data/executive.json'):
    assert (ROOT/'site'/name).exists(),name
assert 'workspace.js' in (ROOT/'site/index.html').read_text(encoding='utf-8')
print('Radar v3:',len(rows),'registres; Balears:',len(bal['records']))
