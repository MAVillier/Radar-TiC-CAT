"""Dated ICT news with original links and content-backed summaries (standard library).

Search feeds discover articles; a search headline is never used as a summary.
NEWS_OFFLINE=1 rebuilds from reviewed articles and quality-v2 cached entries only.
"""
import base64
import concurrent.futures
import datetime as dt
import email.utils
import hashlib
import html
from html.parser import HTMLParser
import ipaddress
import json
import os
import re
import socket
import threading
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from refresh import ROOT

UTC = dt.timezone.utc
BUCKETS = ('ctti', 'generalitat', 'barcelona', 'municipis', 'diba', 'diputacions',
           'competition-cat', 'competition-es', 'competition-world', 'balears')
LABELS = dict(zip(BUCKETS, ('CTTI', 'Generalitat', 'Ajuntament de Barcelona',
    'Ajuntaments de Catalunya', 'Diputació de Barcelona', 'Diputacions de Catalunya',
    'Competència · Catalunya', 'Competència · Espanya', 'Competència · Món', 'Govern Balear')))
WORLDS = {b: ('generalitat' if b in ('ctti', 'generalitat') else
              'competition' if b.startswith('competition-') else 'local') for b in BUCKETS}
QUERIES = [
 ('ctti', '(CTTI OR "Centre de Telecomunicacions i Tecnologies de la Informació") (director OR nomenament OR tecnologia OR projecte OR equip OR contracte) when:365d'),
 ('generalitat', '(site:govern.cat OR site:gencat.cat OR site:aoc.cat) (ciberseguretat OR digitalització OR "intel·ligència artificial" OR TIC) when:180d'),
 ('barcelona', '(site:barcelona.cat OR "Ajuntament de Barcelona") (digitalització OR informàtica OR "intel·ligència artificial" OR ciberseguretat OR "Institut Municipal d’Informàtica") when:180d'),
 ('municipis', '("ajuntaments de Catalunya" OR "ajuntament" OR site:acm.cat OR site:fmc.cat OR site:localret.cat) (digitalització OR ciberseguretat OR informàtica OR "intel·ligència artificial" OR TIC) when:180d'),
 ('diba', '(site:diba.cat OR "Diputació de Barcelona") (digitalització OR ciberseguretat OR informàtica OR "intel·ligència artificial" OR tecnologia) when:180d'),
 ('diputacions', '(site:ddgi.cat OR site:diputaciolleida.cat OR site:dipta.cat) (digitalització OR ciberseguretat OR informàtica OR "intel·ligència artificial" OR tecnologia) when:180d'),
 ('competition-cat', '(Accenture OR Capgemini OR "NTT DATA" OR Inetum OR Minsait OR Seidor OR Deloitte OR "Sopra Steria") (Barcelona OR Catalunya OR Cataluña) (tecnologia OR tecnología OR digital OR cloud OR ciberseguretat OR IA) when:180d'),
 ('competition-es', '(Accenture OR Capgemini OR "NTT DATA" OR Inetum OR Minsait OR Indra OR "Sopra Steria" OR DXC OR Deloitte) (España OR Spain) (tecnología OR digital OR cloud OR ciberseguridad OR IA) when:180d'),
 ('competition-world', '(Accenture OR Capgemini OR "NTT DATA" OR Inetum OR "Sopra Steria" OR DXC OR IBM OR CGI) ("artificial intelligence" OR cloud OR cybersecurity OR "IT services" OR "digital transformation") when:180d'),
 ('balears', '(site:caib.es OR site:fundaciobit.org) (digital OR tecnologia OR ciberseguretat OR informàtica OR "intel·ligència artificial") when:180d')]
FEEDS = [
 ('generalitat', 'https://www.aoc.cat/feed/'),
 ('municipis', 'https://www.localret.cat/feed/'),
 ('balears', 'https://www.fundaciobit.org/feed/'),
 ('competition-world', 'https://www.capgemini.com/feed/'),
]
LISTINGS = [('ctti', 'https://ctti.gencat.cat/ca/inici/'),
            ('ctti', 'https://canigo.ctti.gencat.cat/'),
            ('competition-world', 'https://www.capgemini.com/news/')]
MAX_BYTES = 1_500_000
FETCH_LIMIT = int(os.environ.get('NEWS_FETCH_LIMIT', '90'))
FETCH_COUNT = 0
FETCH_LOCK = threading.Lock()

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()

def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', clean(value).lower()) if not unicodedata.combining(c))

def host(url):
    try:
        return (urllib.parse.urlsplit(url).hostname or '').lower().removeprefix('www.')
    except ValueError:
        return ''

def public_url(url, resolve=False):
    """Reject credentials, local addresses, unusual ports, and unsafe redirect targets."""
    try:
        parsed = urllib.parse.urlsplit(url)
        name = parsed.hostname or ''
        if (parsed.scheme not in ('http', 'https') or not name or parsed.username or parsed.password
                or parsed.port not in (None, 80, 443) or any(c.isspace() for c in url)):
            return False
        if name.lower() == 'localhost' or name.endswith(('.localhost', '.local', '.internal')):
            return False
        try:
            addresses = [ipaddress.ip_address(name)]
        except ValueError:
            if '.' not in name:
                return False
            addresses = [ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(name, parsed.port or 443)] if resolve else []
        return all(a.is_global for a in addresses)
    except (ValueError, OSError):
        return False

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not public_url(newurl, resolve=True):
            raise ValueError('Unsafe redirect')
        return super().redirect_request(request, fp, code, msg, headers, newurl)

def get(url):
    global FETCH_COUNT
    with FETCH_LOCK:
        if FETCH_COUNT >= FETCH_LIMIT:
            raise RuntimeError('News request budget reached')
        FETCH_COUNT += 1
    if not public_url(url, resolve=True):
        raise ValueError('Unsafe URL')
    request = urllib.request.Request(url, headers={'User-Agent': 'RadarTIC/3.0 (public ICT news)', 'Accept': 'text/html,application/rss+xml,application/atom+xml,application/xml;q=0.9'})
    with urllib.request.build_opener(SafeRedirect()).open(request, timeout=9) as response:
        kind = response.headers.get_content_type()
        if kind not in ('text/html', 'application/xhtml+xml', 'application/xml', 'text/xml', 'application/rss+xml', 'application/atom+xml', 'text/plain'):
            raise ValueError('Unsupported news content')
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('News response too large')
        return raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace'), response.url

def parse_date(value):
    if not value:
        return None
    try:
        value = value.strip()
        if re.fullmatch(r'\d{2}/\d{2}/\d{4}', value):
            result = dt.datetime.strptime(value, '%d/%m/%Y')
        else:
            result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        try:
            result = email.utils.parsedate_to_datetime(value)
        except (ValueError, TypeError, AttributeError):
            return None
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)

def fresh(published, bucket, now=None):
    date = parse_date(published)
    now = now or dt.datetime.now(UTC)
    cutoff = (now - dt.timedelta(days=365 if bucket == 'ctti' else 180)).date()
    return bool(date and cutoff <= date.date() and date <= now + dt.timedelta(hours=24))

def original_url(url):
    parsed = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query) if not k.lower().startswith('utm_') and k not in ('fbclid', 'gclid')]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), ''))

def generic_page(url, title=''):
    h = host(url)
    path = urllib.parse.urlsplit(url).path.lower()
    headline = norm(title)
    if path.rstrip('/') in ('', '/ca', '/en', '/es', '/ca/inici', '/en/home', '/es/inicio', '/news', '/noticies', '/ca/actualitat', '/news/press-releases'):
        return True
    if re.fullmatch(r'(noticies|noticias|news|actualitat|actualidad|diari oficial.*|dogc(?:\s*[-·|].*)?|inici|home)', headline):
        return True
    if h in ('news.google.com', 'consent.google.com') or h.endswith('google.com'):
        return True
    if h in ('dogc.gencat.cat', 'dogc.gencat.net', 'portaldogc.gencat.cat'):
        return not ('document-del-dogc' in path or '/document/' in path)
    return bool(re.search(r'/(search|cerca|buscador|tags?|categories?)/', path) or
                re.fullmatch(r'(noticies|noticias|news|actualitat|actualidad|diari oficial.*|dogc|inici|home)', headline))

ICT = re.compile(r'\b(tic|ict|it services|information technolog\w*|digital\w*|tecnolog\w*|technolog\w*|informatic\w*|ciber\w*|cyber\w*|cloud|programari|software|sap|erp|etram|e-tram|administracio electronica|dades obertes|open data|robotitz\w*|robotiz\w*|data cent\w*|intel.ligencia artificial|inteligencia artificial|artificial intelligence|\bia\b|\bai\b|telecomunic\w*|connectivitat|conectividad|microsoft|copilot|automatitz\w*|automatiz\w*)\b')
CTTI = re.compile(r'\bctti\b|centre de telecomunicacions i tecnologies de la informacio')
COMPANIES = re.compile(r'\b(accenture|capgemini|ntt(?: data)?|inetum|minsait|indra|seidor|deloitte|sopra steria|dxc|ibm|cgi|t-systems|t systems|ey|ernst . young|kpmg|pwc|pricewaterhousecoopers|fujitsu|kyndryl|scc|ricoh|telefonica tech|tata consultancy|tcs|infosys|wipro|cognizant|gesa|babel|knowmad mood|izertis|sngular|plain concepts|stratesys|ust)\b')
STRONG_ICT = re.compile(r'\b(tic|ict|it services|information technolog\w*|digital\w*|informatic\w*|ciber\w*|cyber\w*|cloud|programari|software|sap|erp|etram|e-tram|administracio electronica|documents electronics|repositori documental|via oberta|desal|serveis digitals|dades obertes|open data|robotitz\w*|robotiz\w*|data cent\w*|intel.ligencia artificial|inteligencia artificial|artificial intelligence|ia|ai|telecomunic\w*|connectivitat|conectividad|microsoft|copilot|automatitz\w*|automatiz\w*|smishing|ransomware|esquema nacional de seguretat)\b')
CORPORATE_EVENT = re.compile(r'\b(acquir\w*|acquisition\w*|acquisicio\w*|adquisicio\w*|merger|fusio\w*|compra\w*|vend\w*|sell\w*)\b')

def headline_ict(title, summary, bucket, url=''):
    """An ICT word hidden in a site's boilerplate cannot qualify unrelated news."""
    if bucket == 'ctti':
        return True
    headline = norm(title)
    if STRONG_ICT.search(headline + ' ' + norm(summary)):
        return True
    return bool(bucket.startswith('competition-') and COMPANIES.search(headline + ' ' + host(url)) and CORPORATE_EVENT.search(headline))
CATALONIA = re.compile(r'\b(catalunya|cataluna|catalonia|barcelona|girona|lleida|tarragona|sabadell|terrassa|badalona|hospitalet|mataro|reus|sant cugat|granollers|manresa|vic|vilanova|viladecans|castelldefels|cornella|esplugues|sant boi|santa coloma|rubi|igualada|vilafranca|figueres|olot|balaguer|tortosa|amposta|el prat|gava|catalans|catalanes)\b')
SPAIN = re.compile(r'\b(espana|spain|espanyol\w*|espanol\w*|madrid|valencia|sevilla|malaga|bilbao|zaragoza|iberia|iberica|lisboa)\b')

def classify(title, body, url, requested):
    """Validate subject and jurisdiction from article content, not merely the query."""
    text = norm(title + ' ' + body[:4500])
    h = host(url)
    if CTTI.search(text) or h == 'ctti.gencat.cat' or h.endswith('.ctti.gencat.cat'):
        return 'ctti'
    if not (ICT.search(text) or STRONG_ICT.search(text)):
        return None
    if 'diputacio de barcelona' in text or h == 'diba.cat' or h.endswith('.diba.cat'):
        return 'diba'
    if re.search(r'diputacio (de |d[’\x27])?(girona|lleida|tarragona)', text) or h in ('ddgi.cat', 'diputaciolleida.cat', 'dipta.cat'):
        return 'diputacions'
    if ('ajuntament de barcelona' in text or 'institut municipal d’informatica' in text or
            h == 'barcelona.cat' or h.endswith('.barcelona.cat')):
        return 'barcelona'
    if re.search(r'govern (de les illes )?balear|govern de les illes balears|fundacio bit|ibdigital', text) or h in ('caib.es', 'fundaciobit.org') or h.endswith('.caib.es'):
        return 'balears'
    if COMPANIES.search(text + ' ' + h) and requested.startswith('competition-'):
        return 'competition-cat' if CATALONIA.search(text) else 'competition-es' if SPAIN.search(text) else 'competition-world'
    if (re.search(r'\b(ajuntament\w*|municip\w*|localret|govern local)\b', text) and
            (CATALONIA.search(text) or h in ('acm.cat', 'fmc.cat', 'localret.cat', 'aoc.cat'))):
        return 'municipis'
    if ('generalitat' in text and re.search(r'catal|govern.cat|gencat', text + ' ' + h)) or h in ('govern.cat', 'aoc.cat') or h.endswith('.gencat.cat') or h == 'gencat.cat':
        return 'generalitat'
    if COMPANIES.search(text):
        return 'competition-cat' if CATALONIA.search(text) else 'competition-es' if SPAIN.search(text) else 'competition-world'
    return None

BOILERPLATE = re.compile(r'cookies|galetes|accept(ar|a) (totes|todas)|politica de privacitat|privacy policy|subscribe to|subscriu|inicia sessio|javascript|all rights reserved|tots els drets|leer mas|llegeix mes|comparteix (a|en)|share (on|this)|skip to|saltar al|activar accessibilitat', re.I)

def useful_paragraph(value, title=''):
    value = clean(value)
    words = value.split()
    title_words, body_words = set(norm(title).split()), set(norm(value).split())
    repeats_title = len(title_words) >= 8 and len(title_words & body_words) / max(1, len(body_words)) > .82
    return (len(value) >= 90 and len(words) >= 17 and len(value) <= 7000 and
            not BOILERPLATE.search(norm(value)) and norm(value) != norm(title) and not repeats_title and
            len(set(norm(value).split())) >= 12)

def summarize(paragraphs, title=''):
    """A short source excerpt, never a padded headline or invented takeaway."""
    # Rank sentences themselves: a technical word late in a paragraph must not
    # promote its unrelated opening anecdote into the article's summary.
    candidates = []
    for paragraph in paragraphs:
        paragraph = clean(paragraph)
        if not useful_paragraph(paragraph, title):
            continue
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9«“])', paragraph)
        for sentence in sentences:
            if not useful_paragraph(sentence, title) or re.search(r'^(imagina|suposa|pensa en|ella no ho sap|ell no ho sap)', norm(sentence)):
                continue
            candidates.append(sentence)
    ranked = sorted(enumerate(candidates), key=lambda x: (-bool(STRONG_ICT.search(norm(x[1]))), x[0]))
    for _, sentence in ranked:
        words = sentence.split()
        excerpt = ' '.join(words[:24]) + ('…' if len(words) > 24 else '')
        if useful_paragraph(excerpt, title):
            return excerpt
    return ''

class ArticleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.links, self.paragraphs, self.article_paragraphs = {}, [], [], []
        self.content_paragraphs, self.regions = [], []
        self.stack, self.capture, self.text, self.anchor = [], None, [], None
        self.title, self.times = '', []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        # Void elements must not leak into the structural stack.
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.stack.append(tag)
            self.regions.append((a.get('class', '') + ' ' + a.get('id', '')).lower())
        if tag == 'meta':
            self.meta[(a.get('property') or a.get('name') or '').lower()] = a.get('content', '')
        if tag == 'link' and a.get('rel') == 'canonical':
            self.meta['canonical'] = a.get('href', '')
        if tag == 'time' and a.get('datetime') and ('article' in self.stack or 'main' in self.stack):
            self.times.append(a['datetime'])
        if tag == 'a' and a.get('href'):
            self.anchor = [a['href'], [], a.get('aria-label') or a.get('title', '')]
        blocked = any(re.search(r'related|post-loop|sidebar|recommend|newsletter|subscribe', region) for region in self.regions)
        if tag in ('p', 'title') and not blocked and not any(t in self.stack for t in ('nav', 'footer', 'aside', 'script', 'style', 'noscript')):
            self.capture, self.text = tag, []

    def handle_data(self, data):
        if self.capture:
            self.text.append(data)
        if self.anchor:
            self.anchor[1].append(data)

    def handle_endtag(self, tag):
        if self.capture == tag:
            text = clean(' '.join(self.text))
            if tag == 'title':
                self.title = text
            elif text:
                self.paragraphs.append(text)
                if any(re.search(r'entry-content|article-body|post-content|single-blog__content-main|news-content', region) for region in self.regions):
                    self.content_paragraphs.append(text)
                if 'article' in self.stack or 'main' in self.stack:
                    self.article_paragraphs.append(text)
            self.capture, self.text = None, []
        if tag == 'a' and self.anchor:
            self.links.append((self.anchor[0], clean(' '.join(self.anchor[1])) or clean(self.anchor[2])))
            self.anchor = None
        if tag in self.stack:
            end = len(self.stack) - 1 - self.stack[::-1].index(tag)
            self.stack = self.stack[:end]
            self.regions = self.regions[:end]

def json_articles(raw):
    def walk(value):
        if isinstance(value, dict):
            kinds = value.get('@type', [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if any(k in ('Article', 'NewsArticle', 'BlogPosting', 'TechArticle', 'ReportageNewsArticle') for k in kinds):
                yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)
    for data in re.findall(r'<script\b[^>]*type=["\x27]application/ld\+json["\x27][^>]*>(.*?)</script>', raw, re.I | re.S):
        try:
            yield from walk(json.loads(data))
        except (ValueError, TypeError):
            pass

def article_data(raw, url):
    parser = ArticleHTML()
    parser.feed(raw)
    structured = next(iter(json_articles(raw)), {})
    title = clean(structured.get('headline') or parser.meta.get('og:title') or parser.title)
    paragraphs = []
    if structured.get('articleBody'):
        paragraphs.extend(str(structured['articleBody']).split('\n'))
    paragraphs.extend(parser.content_paragraphs or parser.article_paragraphs or parser.paragraphs)
    summary = summarize(paragraphs, title)
    kind = 'extractive'
    if not summary:
        summary = summarize([parser.meta.get('og:description', ''), parser.meta.get('description', '')], title)
        kind = 'publisher'
    date = parse_date(structured.get('datePublished') or parser.meta.get('article:published_time') or
                      parser.meta.get('publish-date') or parser.meta.get('parsely-pub-date') or
                      parser.meta.get('date') or parser.meta.get('datepublished') or next(iter(parser.times), ''))
    # Canigó encodes the publication day in its dated news URL. Do not use a
    # page's modification time to make an old article look newly published.
    if not date and host(url) == 'canigo.ctti.gencat.cat':
        slug_date = re.search(r'/noticies/(\d{4}-\d{2}-\d{2})', url)
        date = parse_date(slug_date[1]) if slug_date else None
    canonical = urllib.parse.urljoin(url, parser.meta.get('canonical') or url)
    if host(canonical) != host(url) or not public_url(canonical):
        canonical = url
    return {'title': title, 'summary': summary, 'summaryKind': kind,
            'body': '\n'.join(paragraphs), 'published': date.isoformat() if date else None,
            'url': original_url(canonical), 'links': parser.links}

def parse_feed(raw, bucket, feed_url):
    tree = ET.fromstring(raw)
    result = []
    for entry in tree.iter():
        if entry.tag.split('}')[-1] not in ('item', 'entry'):
            continue
        values, link, publisher_url = {}, '', ''
        for element in entry:
            name = element.tag.split('}')[-1]
            text = ''.join(element.itertext())
            values[name] = text
            if name == 'link' and element.get('rel', 'alternate') == 'alternate':
                link = element.get('href') or text
            if name == 'source':
                publisher_url = element.get('url', '')
        title = clean(values.get('title'))
        source = clean(values.get('source')) or host(feed_url)
        if title.endswith(' - ' + source):
            title = title[:-(len(source) + 3)]
        published = parse_date(values.get('pubDate') or values.get('published') or values.get('date'))
        if not title or not public_url(link) or not published or not fresh(published.isoformat(), bucket):
            continue
        content = values.get('encoded') or values.get('content') or values.get('description') or values.get('summary') or ''
        result.append({'title': title, 'url': link, 'published': published.isoformat(), 'bucket': bucket,
                       'source': source, 'publisherUrl': publisher_url, 'content': content})
    return result

def resolve_google(candidate):
    url = candidate['url']
    if host(url) != 'news.google.com':
        return url, None
    token = urllib.parse.urlsplit(url).path.rsplit('/', 1)[-1]
    try:
        decoded = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)).decode('utf-8', errors='ignore')
        for direct in re.findall(r'https?://[^\s\x00-\x20\x7f-\uffff<>"\x27]+', decoded):
            if public_url(direct) and not generic_page(direct):
                return direct, None
    except ValueError:
        pass
    raw, final = get(url)
    if host(final) != 'news.google.com' and not generic_page(final):
        return final, raw
    parser = ArticleHTML()
    parser.feed(raw)
    publisher = host(candidate.get('publisherUrl', ''))
    for link, _ in parser.links:
        if publisher and host(link) == publisher and public_url(link) and urllib.parse.urlsplit(link).path not in ('', '/'):
            return link, None
    raise ValueError('Original publisher URL unavailable')

def make_item(candidate, fetch=True):
    url, prefetched = resolve_google(candidate) if fetch else (candidate['url'], None)
    if generic_page(url):
        return None
    # Full direct-feed article content may already carry the actual article body.
    content = candidate.get('content', '')
    parser = ArticleHTML()
    parser.feed(content)
    paragraphs = parser.content_paragraphs or parser.article_paragraphs or parser.paragraphs or [content]
    body = '\n'.join(clean(p) for p in paragraphs)
    summary = summarize(paragraphs, candidate['title'])
    kind = 'publisher'
    if not summary and fetch:
        raw, final = (prefetched, url) if prefetched is not None else get(url)
        article = article_data(raw, final)
        url, summary, body, kind = article['url'], article['summary'], article['body'], article['summaryKind']
        if article['title'] and generic_page(url, candidate['title']):
            candidate = {**candidate, 'title': article['title']}
        if article['published']:
            candidate = {**candidate, 'published': article['published']}
    if not summary or generic_page(url, candidate['title']):
        return None
    bucket = classify(candidate['title'], body + ' ' + summary, url, candidate['bucket'])
    if not bucket or not fresh(candidate.get('published'), bucket):
        return None
    lead = '\n'.join(body.split('\n')[:2])
    if not headline_ict(candidate['title'], lead, bucket, url) or not headline_ict(candidate['title'], summary, bucket, url):
        return None
    url = original_url(url)
    return {'id': hashlib.sha256(url.encode()).hexdigest()[:18], 'title': clean(candidate['title']),
            'summary': summary, 'url': url, 'source': candidate.get('source') or host(url),
            'published': candidate['published'], 'world': WORLDS[bucket], 'bucket': bucket,
            'topic': LABELS[bucket], 'summaryKind': kind, 'qualityVersion': 2,
            'contentBucket': bucket}

def validated_item(item, reviewed=False, now=None):
    """Old headline-only cache entries are intentionally never promoted to v2."""
    if not isinstance(item, dict) or (not reviewed and item.get('qualityVersion') != 2):
        return None
    bucket, url = item.get('bucket'), item.get('url', '')
    if bucket not in BUCKETS or not public_url(url) or generic_page(url, item.get('title', '')):
        return None
    if not fresh(item.get('published'), bucket, now) or not useful_paragraph(item.get('summary', ''), item.get('title', '')):
        return None
    if item.get('summaryKind') not in ('extractive', 'publisher', 'reviewed'):
        return None
    if not headline_ict(item.get('title', ''), item.get('summary', ''), bucket, url):
        return None
    actual_bucket = classify(item.get('title', ''), item.get('summary', ''), url, bucket)
    if actual_bucket != bucket and not (item.get('contentBucket') == bucket or reviewed):
        return None
    if reviewed and not (ICT.search(norm(item.get('title', '') + ' ' + item.get('summary', ''))) or STRONG_ICT.search(norm(item.get('title', '') + ' ' + item.get('summary', ''))) or bucket == 'ctti'):
        return None
    result = {k: item[k] for k in ('title', 'summary', 'url', 'source', 'published', 'summaryKind') if k in item}
    if item.get('dateKind') == 'updated':
        result['dateKind'] = 'updated'
    result.update(id=hashlib.sha256(original_url(url).encode()).hexdigest()[:18], bucket=bucket,
                  world=WORLDS[bucket], topic=LABELS[bucket], qualityVersion=2, contentBucket=bucket, url=original_url(url))
    if reviewed:
        result['summaryKind'] = 'reviewed'
    return result

def merge_items(old, fresh_items, reviewed, now=None):
    unique = {}
    for group, is_reviewed in ((old, False), (fresh_items, False), (reviewed, True)):
        for item in group:
            accepted = validated_item(item, is_reviewed, now)
            if accepted:
                unique[accepted['url']] = accepted
    by_title = {norm(i['title']): i for i in sorted(unique.values(), key=lambda i: i['summaryKind'] == 'reviewed')}
    # Priority is the requested editorial order; dates descend inside each bucket.
    ordered = sorted(by_title.values(), key=lambda i: (BUCKETS.index(i['bucket']), -parse_date(i['published']).timestamp(), i['title']))
    result, per_bucket, urls = [], {}, set()
    for item in ordered:
        count = per_bucket.get(item['bucket'], 0)
        if count < 30 and item['url'] not in urls:
            result.append(item)
            urls.add(item['url'])
            per_bucket[item['bucket']] = count + 1
    return result

def listing_candidates(raw, url, bucket):
    parser = ArticleHTML()
    parser.feed(raw)
    result = []
    seen = set()
    for href, title in parser.links:
        link = urllib.parse.urljoin(url, href)
        if (host(link) == host(url) and public_url(link) and len(title.split()) >= 5 and
                re.search(r'/notici[ae]|/detall/noticia|/actualitat/.+|/news/press-releases/.+', urllib.parse.urlsplit(link).path) and
                link not in seen and not generic_page(link, title)):
            seen.add(link)
            result.append({'url': link, 'title': title, 'bucket': bucket, 'source': LABELS[bucket], 'content': '', 'published': None})
    return result[:12]

def main():
    target = ROOT / 'site/data/news.json'
    seed = ROOT / 'site/data/news-reviewed.json'
    old = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    reviewed = json.loads(seed.read_text(encoding='utf-8')) if seed.exists() else {}
    reviewed = reviewed if isinstance(reviewed, list) else reviewed.get('items', [])
    offline = os.environ.get('NEWS_OFFLINE') == '1'
    sources, items, candidates = [], [], []
    if not offline:
        def discover(task):
            bucket, url, mode = task
            try:
                raw, final = get(url)
                rows = listing_candidates(raw, final, bucket) if mode == 'listing' else parse_feed(raw, bucket, final)
                return rows, {'name': LABELS[bucket], 'bucket': bucket, 'url': url, 'ok': True, 'discovered': len(rows)}
            except Exception as exc:
                return [], {'name': LABELS[bucket], 'bucket': bucket, 'url': url, 'ok': False, 'error': type(exc).__name__}
        tasks = [(b, u, 'listing') for b, u in LISTINGS] + [(b, u, 'feed') for b, u in FEEDS]
        tasks += [(b, 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q': q, 'hl': 'ca', 'gl': 'ES', 'ceid': 'ES:ca'}), 'feed') for b, q in QUERIES]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for rows, status in pool.map(discover, tasks):
                candidates.extend(rows)
                sources.append(status)
        # Reserve discovery order for direct sources, then give each bucket a fair share.
        counts, seen = {}, set()
        selected = []
        for candidate in candidates:
            bucket, url = candidate['bucket'], candidate['url']
            if url not in seen and counts.get(bucket, 0) < (12 if bucket == 'ctti' else 6):
                selected.append(candidate)
                seen.add(url)
                counts[bucket] = counts.get(bucket, 0) + 1
        def enrich(candidate):
            try:
                return make_item(candidate)
            except Exception:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            items = [item for item in pool.map(enrich, selected) if item]
    result_items = merge_items(old.get('items', []) if old.get('version') == 2 else [], items, reviewed)
    result = {'version': 2, 'generated': dt.datetime.now(UTC).isoformat(),
              'lastFetched': dt.datetime.now(UTC).isoformat() if not offline and any(s['ok'] for s in sources) else old.get('lastFetched'),
              'sources': old.get('sources', []) if offline else sources,
              'buckets': [{'id': b, 'label': LABELS[b], 'world': WORLDS[b]} for b in BUCKETS],
              'diagnostics': {'offline': offline, 'discovered': len(candidates), 'contentAccepted': len(items),
                              'reviewedAccepted': len(merge_items([], [], reviewed)), 'requests': FETCH_COUNT},
              'items': result_items}
    if not result_items and not offline and not any(s['ok'] for s in sources):
        raise RuntimeError('No accessible news source or valid reviewed article')
    target.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('Notícies:', len(result_items), '; articles amb contingut:', len(items), '; mode:', 'local' if offline else 'fonts', flush=True)

if __name__ == '__main__':
    main()
