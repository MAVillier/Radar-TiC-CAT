"""Import recent ICT tenders from MC Mutual's public eContrata portal."""
import datetime as dt
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None
from refresh import ROOT

ROOT_URL = 'https://econtrata.mc-mutual.com'
SITES = (('6', 'Divisió de Tecnologia'), ('5', 'Divisió de Transformació'))
MONTHS = {
    'ene': 1, 'jan': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'apr': 4, 'may': 5,
    'jun': 6, 'jul': 7, 'ago': 8, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12, 'dec': 12,
}

def fetch(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'RadarTIC/3.0 public procurement',
        'Accept': 'text/html,application/xhtml+xml',
    })
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read(4_000_000)
                if len(raw) >= 4_000_000:
                    raise ValueError('Resposta massa gran')
                return raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace'), response.url
        except Exception as error:
            last = error
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f'No s’ha pogut llegir {url}: {type(last).__name__}: {last}') from last

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()

def first(pattern, text):
    match = re.search(pattern, text, re.I | re.S)
    return clean(match.group(1)) if match else ''

def amount(value):
    value = re.sub(r'[^0-9,.-]', '', value or '').strip()
    if not value:
        return None
    if ',' in value:
        value = value.replace('.', '').replace(',', '.')
    try:
        number = float(value)
        return number if number >= 0 else None
    except ValueError:
        return None

def madrid_iso(value):
    match = re.fullmatch(r'(\d{2})/([a-z]{3})/(\d{4})\s+(\d{2}):(\d{2})', value.strip(), re.I)
    if not match:
        return None
    day, mon, year, hour, minute = match.groups()
    month = MONTHS.get(mon.lower())
    if not month:
        return None
    local = dt.datetime(int(year), month, int(day), int(hour), int(minute))
    if ZoneInfo:
        try:
            return local.replace(tzinfo=ZoneInfo('Europe/Madrid')).isoformat()
        except Exception:
            pass
    def last_sunday(month):
        last = (dt.datetime(int(year), month, 28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
        return last.day - (last.weekday() + 1) % 7
    summer_start = dt.datetime(int(year), 3, last_sunday(3), 2)
    summer_end = dt.datetime(int(year), 10, last_sunday(10), 3)
    offset = 2 if summer_start <= local < summer_end else 1
    return local.replace(tzinfo=dt.timezone(dt.timedelta(hours=offset))).isoformat()

def phase(status):
    value = clean(status).lower()
    if 'public' in value or 'plazo' in value:
        return 'Anunci de licitació'
    if 'evalu' in value or 'valorac' in value or 'pendiente' in value:
        return 'Expedient en avaluació'
    if 'adjudic' in value:
        return 'Adjudicació'
    if 'formaliz' in value or 'formalitz' in value:
        return 'Formalització'
    if 'desiert' in value:
        return 'Desert'
    if 'anulad' in value or 'cancel' in value:
        return 'Anul·lació'
    if 'cerrad' in value or 'finaliz' in value or 'resuelt' in value:
        return 'Resolt'
    return status or 'Expedient en avaluació'

def parse_cards(raw, site, division):
    text = raw
    parts = re.split(r'<div\s+class=[\"\']panel panel-default[\"\']\s*>', text, flags=re.I)
    rows = []
    for block in parts[1:]:
        if 'media-heading' not in block:
            continue
        code = first(r"<p[^>]*class=[\"\']media-heading h4[\"\'][^>]*>(.*?)</p>", block)
        title = first(r'<i[^>]*>(.*?)</i>', block)
        href = first(r'<a[^>]*href=[\"\']([^\"\']*licitaciones/detalle\?id=\d+)[\"\']', block)
        if not code or not title or not href:
            continue
        budget_match = re.search(r'<strong>\s*Presupuesto sin impuestos\s*</strong>\s*<div[^>]*>\s*<span[^>]*>(.*?)</span>\s*<span[^>]*>\s*EUR', block, re.I | re.S)
        budget = amount(clean(budget_match.group(1))) if budget_match else None
        status = first(r'<strong>\s*Estado\s*</strong>\s*<span[^>]*>(.*?)</span>', block)
        vigencia = first(r'<strong>\s*Vigencia del trámite\s*</strong>.*?<span[^>]*>(.*?)</span>', block)
        dates = re.match(r'(.+?)\s*-\s*(.+)$', vigencia)
        published = madrid_iso(dates.group(1)) if dates else None
        deadline = madrid_iso(dates.group(2)) if dates else None
        organizer = first(r'<span>\s*Organizado por\s*</span>\s*<a[^>]*>.*?<span[^>]*>(.*?)</span>', block) or division
        contract_type = first(r'<strong[^>]*>\s*Tipo de Contrato\s*</strong>\s*<span[^>]*>(.*?)</span>', block)
        procedure = first(r'<strong>\s*Tipo de Procedimiento\s*</strong>\s*<span[^>]*>(.*?)</span>', block)
        detail = urllib.parse.urljoin(ROOT_URL, html.unescape(href).replace('&amp;', '&'))
        rows.append({
            'id': f'mcmutual|{site}|{code}', 'exp': code, 'organCode': f'mcmutual:{site}',
            'organ': 'MC Mutual', 'scope': f'MC Mutual · {organizer}', 'world': 'other',
            'territory': 'catalunya', 'lot': '', 'lotTitle': '', 'title': title,
            'description': title, 'cpv': [], 'tic': True, 'phase': phase(status), 'result': status,
            'procedure': procedure, 'rationalization': '', 'budget': budget, 'contractBudget': budget,
            'vec': None, 'awarded': None, 'winner': '', 'offers': None, 'deadline': deadline,
            'published': published, 'awardDate': None, 'duration': '', 'endDate': None,
            'discount': {'value': None, 'reason': ''}, 'source': detail,
            'sourceQuery': f'{ROOT_URL}/site/{site}/licitacion/licitaciones/',
            'documents': {}, 'rawHash': hashlib.sha256(block.encode('utf-8')).hexdigest(),
            'candidates': [], 'terms': {'duration': '', 'vec': None, 'criteria': [],
                'extensionText': '', 'extensionAllowed': None},
            'attachments': [],
        })
    return rows

def parse_documents(raw, detail_url):
    start = raw.find('id="divDocumentos"')
    if start < 0:
        start = raw.find("id='divDocumentos'")
    if start < 0:
        return []
    section = raw[start:]
    end = section.find('id="divAnuncios"')
    if end >= 0:
        section = section[:end]
    attachments = []
    for row in re.findall(r'<tr\b.*?</tr>', section, re.I | re.S):
        href = first(r'<a[^>]*href=["\']([^"\']*licitacion/documento[^"\']*)["\']', row)
        if not href:
            continue
        title = first(r'<strong[^>]*>(.*?)</strong>', row)
        description = first(r'<p[^>]*>(.*?)</p>', row)
        label = ' · '.join(value for value in (title, description) if value)
        attachments.append({'title': label or 'Document de licitació',
                            'url': urllib.parse.urljoin(detail_url, html.unescape(href).replace('&amp;', '&'))})
    return attachments

def main():
    target = ROOT / 'site/data/mcmutual.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    state = {row['id']: row for row in old.get('records', [])}
    pages_ok = 0
    fresh_ids = set()
    sources = []
    for site, division in SITES:
        empty = 0
        for page in range(0, 32):
            url = f'{ROOT_URL}/site/{site}/licitacion/licitaciones/?' + urllib.parse.urlencode({
                'page': page, 'term': '',
            })
            try:
                raw, final = fetch(url)
            except Exception as error:
                print('MC Mutual pàgina no disponible:', site, page, type(error).__name__, flush=True)
                break
            pages_ok += 1
            cards = parse_cards(raw, site, division)
            sources.append(final)
            if not cards:
                empty += 1
                if empty >= 2:
                    break
                continue
            empty = 0
            for row in cards:
                if row['id'] in fresh_ids:
                    continue
                previous = state.get(row['id'], {})
                old_attachments = previous.get('attachments', [])
                needs_detail = not old_attachments
                if old_attachments and row.get('deadline') and row.get('phase') in ('Anunci de licitació', 'Expedient en avaluació'):
                    try:
                        deadline = dt.datetime.fromisoformat(row['deadline'])
                        if deadline.tzinfo is None:
                            deadline = deadline.replace(tzinfo=dt.timezone(dt.timedelta(hours=1)))
                        needs_detail = deadline > dt.datetime.now(dt.timezone.utc).astimezone(deadline.tzinfo)
                    except ValueError:
                        needs_detail = False
                row['attachments'] = old_attachments
                if needs_detail:
                    try:
                        detail, final_detail = fetch(row['source'])
                        row['attachments'] = parse_documents(detail, final_detail)
                        row['source'] = final_detail
                    except Exception as error:
                        print('MC Mutual detall no disponible:', row['exp'], type(error).__name__, flush=True)
                state[row['id']] = row
                fresh_ids.add(row['id'])
    if not fresh_ids and not state:
        raise RuntimeError('El portal de MC Mutual no ha retornat cap licitació i no hi ha dades anteriors per conservar')
    records = sorted(state.values(), key=lambda row: (row.get('published') or '', row['id']), reverse=True)
    result = {
        'generated': dt.datetime.now(dt.timezone.utc).isoformat(),
        'source': ROOT_URL,
        'sources': list(dict.fromkeys(sources)),
        'pagesRead': pages_ok,
        'records': records,
    }
    target.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('MC Mutual:', len(records), 'licitacions; noves o actualitzades:', len(fresh_ids), '; pàgines:', pages_ok, flush=True)

if __name__ == '__main__':
    main()
