"""Daily public-source discovery feed; links lead to the official publications."""
import datetime as dt,gzip,json,email.utils,xml.etree.ElementTree as E
from refresh import ROOT
D=ROOT/'site/data'
def main():
 data=json.loads(gzip.decompress((D/'catalog.json.gz').read_bytes()))
 root=E.Element('rss',version='2.0');channel=E.SubElement(root,'channel')
 for k,v in [('title','Radar TIC · Novetats'),('link','https://contractaciopublica.cat'),('description','Licitacions TIC de Catalunya i del Govern Balear'),('language','ca')]:E.SubElement(channel,k).text=v
 rows=sorted((r for r in data['records'] if r['tic'] and r['world'] in ('generalitat','local')),key=lambda r:r.get('noticePublished') or r.get('published') or '',reverse=True)[:100]
 for r in rows:
  item=E.SubElement(channel,'item');E.SubElement(item,'guid',isPermaLink='false').text=r['key']+'|'+(r.get('noticePublished') or r.get('published') or '')
  for k,v in [('title',r['shortTitle']),('link',r['source']),('description',r['organ']+' · '+r['exp']+' · '+r['phase'])]:E.SubElement(item,k).text=v
  try:
   date=dt.datetime.fromisoformat(r.get('noticePublished') or r['published']);date=date.replace(tzinfo=dt.timezone.utc) if date.tzinfo is None else date
   E.SubElement(item,'pubDate').text=email.utils.format_datetime(date)
  except (ValueError,TypeError):pass
 E.ElementTree(root).write(ROOT/'site/updates.xml',encoding='utf-8',xml_declaration=True)
if __name__=='__main__':main()
