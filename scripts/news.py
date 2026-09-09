"""Headlines with original publisher and date; no invented article summaries."""
import concurrent.futures,datetime as dt,email.utils,hashlib,html,json,re,urllib.parse,urllib.request,xml.etree.ElementTree as E
from refresh import ROOT
QUERIES=[('generalitat','Generalitat · Tecnologia','(site:govern.cat OR site:gencat.cat) (digital OR ciberseguretat OR CTTI OR tecnologia OR intel·ligència) when:60d'),
('local','Ajuntaments · Tecnologia','(site:barcelona.cat OR site:girona.cat OR site:paeria.cat OR site:tarragona.cat) (digital OR tecnologia OR informàtica OR intel·ligència) when:60d'),
('local','Diputacions · Tecnologia','(site:diba.cat OR site:ddgi.cat OR site:diputaciolleida.cat OR site:dipta.cat) (digital OR tecnologia OR ciberseguretat OR informàtica) when:60d'),
('local','Govern Balear · Tecnologia','(site:caib.es OR site:fundaciobit.org OR site:ibdigital.caib.es) (digital OR tecnología OR tecnologia OR ciberseguridad OR licitació) when:60d')]
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 RadarTIC'}),timeout=35) as r:return r.read()
def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',s or ''))).strip()
def parse(raw,world,label):
 root=E.fromstring(raw);out=[];now=dt.datetime.now(dt.timezone.utc)
 for item in root.findall('.//item'):
  title=clean(item.findtext('title'));source=clean(item.findtext('source')) or label;link=item.findtext('link') or '';published=item.findtext('pubDate')
  try:date=email.utils.parsedate_to_datetime(published).astimezone(dt.timezone.utc)
  except (ValueError,TypeError,AttributeError):continue
  if date>now+dt.timedelta(hours=24) or date<now-dt.timedelta(days=65):continue
  if not title or not link.startswith('https://'):continue
  if title.endswith(' - '+source):title=title[:-(len(source)+3)]
  out.append({'id':hashlib.sha256(link.encode()).hexdigest()[:18],'world':world,'title':title,'source':source,'url':link,'published':date.isoformat(),'topic':label})
 return out
def main():
 target=ROOT/'site/data/news.json';old=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'items':[]};items=[];sources=[]
 def work(q):
  world,label,query=q;url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':'ca','gl':'ES','ceid':'ES:ca'})
  try:return parse(get(url),world,label),{'name':label,'url':url,'ok':True}
  except Exception as e:return [],{'name':label,'url':url,'ok':False,'error':type(e).__name__}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for rows,status in pool.map(work,QUERIES):items+=rows;sources.append(status)
 # Direct official feeds supplement news discovery, particularly instrumental bodies.
 for world,label,url in [('generalitat','Administració Oberta de Catalunya','https://www.aoc.cat/feed/'),('local','Fundació BIT','https://www.fundaciobit.org/feed/')]:
  try:items+=parse(get(url),world,label);sources.append({'name':label,'url':url,'ok':True})
  except Exception as e:sources.append({'name':label,'url':url,'ok':False,'error':type(e).__name__})
 if not any(s['ok'] for s in sources):raise RuntimeError('Cap font de notícies accessible')
 # Retain dated earlier entries if a feed is temporarily unavailable.
 unique={i['id']:i for i in old['items']};unique.update({i['id']:i for i in items});cutoff=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=65)).isoformat()
 result={'generated':dt.datetime.now(dt.timezone.utc).isoformat(),'sources':sources,'items':sorted([i for i in unique.values() if i['published']>=cutoff],key=lambda i:i['published'],reverse=True)[:160]}
 target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8');print('Notícies:',len(result['items']),'; fonts:',sum(s['ok'] for s in sources),'/',len(sources),flush=True)
if __name__=='__main__':main()
