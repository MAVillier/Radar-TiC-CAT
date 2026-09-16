"""Extract contract provisions and net financial table rows with page evidence."""
import re, unicodedata
from decimal import Decimal

WORDS={'un':1,'una':1,'dos':2,'dues':2,'tres':3,'quatre':4,'cuatro':4,'cinc':5,'cinco':5,'sis':6,'seis':6,'set':7,'vuit':8,'nou':9,'deu':10,'dotze':12,'doce':12,'divuit':18,'vint-i-quatre':24,'trenta-sis':36}
NUMBER=r'(?:\d+|vint-i-quatre|trenta-sis|divuit|dotze|doce|quatre|cuatro|cinco|dues|tres|cinc|seis|dos|una|un|sis|set|vuit|nou|deu)(?:\s*\(\s*\d+\s*\))?'
UNIT=r'(?:mesos|meses|mes|anys?|anos?)'
MONEY=r'(?<![\d.,])(?:\d{1,3}(?:[. ]\d{3})+|\d+),\d{2}(?!\d)'
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn')
def flat(s):return re.sub(r'\s+',' ',s).strip()
def number(s):
 n=re.search(r'\((\d+)\)',s) or re.search(r'(\d+)',s)
 return int(n[1]) if n else WORDS[s.strip()]
def months(n,u):return number(n)*(12 if u.startswith(('any','ano')) else 1)
def euro(s):return Decimal(s.replace('.','').replace(' ','').replace(',','.'))

def extract_terms(pages):
 evidence=[];rows=[];counts=set();previous_lines=[];previous_page=None
 def add(field,value,page,text):evidence.append({'field':field,'value':value,'page':page,'text':flat(text)[:400],'scope':'unspecified'})
 for item in pages:
  page,original=item[:2];layout=item[2] if len(item)>2 else original
  text=flat(norm(original))
  pattern=rf'({NUMBER})\s+prorrog(?:ues|as?)\s+(?:(?:successives|sucesivas)\s+)?(?:de|d[’\x27])\s*({NUMBER})\s+({UNIT})'
  for m in re.finditer(pattern,text):
   # A quantified contract provision, not the boilerplate "if provided in the QC".
   if re.search(r'no\s+(?:es\s+preveu|s.admet)[^.]{0,50}$',text[max(0,m.start()-80):m.start()]):continue
   count=number(m[1]);each=months(m[2],m[3]);counts.add(count)
   if count<1 or each<1:continue
   for field,value in [('extensionAllowed',True),('extensionCount',count),('extensionMonthsEach',each),('extensionMonths',count*each)]:add(field,value,page,m[0])
  for m in re.finditer(rf'(?:durada inicial(?: del contracte)?\s+(?:sera|es)\s+(?:de\s+)?|termini\s*:\s*)({NUMBER})\s+({UNIT})',text):
   add('durationMonths',months(m[1],m[2]),page,m[0])
  prefix=previous_lines[-25:] if previous_page==page-1 else []
  current_lines=layout.splitlines();lines=prefix+current_lines
  previous_lines=current_lines;previous_page=page
  for index in range(len(prefix),len(lines)):
   line=lines[index]
   amounts=list(re.finditer(MONEY,line))
   if not amounts:continue
   label=flat(norm(line[:amounts[0].start()]))
   if not re.search(r'prorrog|modificaci',label):continue
   # A row must start with a financial label; prose and VAT-inclusive columns are not amounts.
   if not re.match(r'(?:(?:primera|segona|tercera|quarta|1a|2a|3a|4a)\s+)?(?:prorrog|modificaci|import.*(?:prorrog|modificaci))',label):continue
   column=None
   for header in reversed(lines[max(0,index-20):index]):
    cells=re.findall(r'IVA\s+(?:excl[oò]s|incl[oò]s)|sense\s+IVA|amb\s+IVA|\b21\s*%',header,re.I)
    if cells and any(re.search(r'excl|sense',x,re.I) for x in cells):
     column=next(i for i,c in enumerate(cells) if re.search(r'excl|sense',c,re.I));break
   if column is None or column>=len(amounts):continue
   amount=euro(amounts[column][0]);field='extensionAmount' if 'prorrog' in label else 'modificationAmount'
   ordinal=re.match(r'(primera|segona|tercera|quarta|1a|2a|3a|4a)\b',label)
   rows.append((field,ordinal[1] if ordinal else 'total',amount,page,line))
 # Deduplicate repeated tables, including the repetition in the contract-modification clause.
 for field in ('extensionAmount','modificationAmount'):
  relevant=[r for r in rows if r[0]==field];totals={r[2] for r in relevant if r[1]=='total'}
  for amount in totals:
   row=next(r for r in relevant if r[2]==amount and r[1]=='total');add(field,float(amount),row[3],row[4])
  parts={}
  for row in relevant:
   if row[1]!='total':parts.setdefault(row[1],set()).add(row[2])
  if field=='extensionAmount' and len(counts)==1 and len(parts)==next(iter(counts)) and all(len(v)==1 for v in parts.values()):
   total=sum((next(iter(v)) for v in parts.values()),Decimal(0))
   part_rows=[r for r in relevant if r[1]!='total']
   add(field,float(total),sorted({r[3] for r in part_rows}),' + '.join(flat(r[4]) for r in part_rows[:len(parts)]))
 for field,flag in [('extensionAmount','extensionAllowed'),('modificationAmount','modificationAllowed')]:
  for ev in list(evidence):
   if ev['field']==field:add(flag,ev['value']>0,ev['page'],ev['text'])
 return evidence
