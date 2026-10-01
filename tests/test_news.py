import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import news

NOW = dt.datetime(2026, 9, 16, tzinfo=dt.timezone.utc)
BODY = ('El CTTI ha presentat nous serveis digitals que permetran als departaments '
        'millorar la gestió dels seus sistemes informàtics i reforçar-ne la seguretat.')

def item(**changes):
    result = dict(title='El CTTI presenta nous serveis digitals', summary=BODY,
                  url='https://ctti.gencat.cat/ca/detall/noticia/2026/09/serveis',
                  source='CTTI', published='2026-09-10T10:00:00+00:00', bucket='ctti',
                  summaryKind='reviewed', qualityVersion=2)
    result.update(changes)
    return result

class NewsTests(unittest.TestCase):
    def test_old_headlines_are_not_retained(self):
        old = item()
        old.pop('qualityVersion')
        self.assertEqual(news.merge_items([old], [], [], NOW), [])

    def test_summaries_are_required(self):
        self.assertIsNone(news.validated_item(item(summary='El CTTI presenta nous serveis digitals'), now=NOW))
        self.assertIsNone(news.validated_item(item(summary='Accepta totes les galetes ' * 12), now=NOW))

    def test_reviewed_seed_keeps_real_publication_date_and_overrides(self):
        revised = item(summary=BODY + ' La notícia concreta les actuacions previstes per a aquest any.')
        merged = news.merge_items([item()], [], [revised], NOW)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['summary'], revised['summary'])
        self.assertEqual(merged[0]['published'], revised['published'])

    def test_ctti_window_is_longer_and_future_articles_rejected(self):
        self.assertTrue(news.fresh('2026-01-10', 'ctti', NOW))
        self.assertFalse(news.fresh('2026-01-10', 'barcelona', NOW))
        self.assertFalse(news.fresh('2026-10-10', 'ctti', NOW))

    def test_people_at_ctti_are_in_scope_without_generic_technology_keyword(self):
        self.assertEqual(news.classify('Nou nomenament al CTTI', 'La directora assumeix la responsabilitat del centre.', 'https://example.org/news/directora', 'generalitat'), 'ctti')
        self.assertEqual(news.classify('Orquestrador de releases', 'Nova funcionalitat del servei SIC+', 'https://canigo.ctti.gencat.cat/noticies/2026-09-01-release/', 'ctti'), 'ctti')

    def test_non_ict_municipal_news_is_rejected(self):
        self.assertIsNone(news.classify('Barcelona estrena una pista esportiva', 'L’Ajuntament de Barcelona amplia els equipaments de barri.', 'https://barcelona.cat/noticia/pista', 'barcelona'))

    def test_institutional_order_and_provenance(self):
        self.assertEqual(news.classify('Nous serveis de ciberseguretat', 'La Diputació de Barcelona dona suport als ajuntaments.', 'https://diba.cat/noticia/ciber', 'municipis'), 'diba')
        self.assertEqual(news.classify('Lleida reforça la ciberseguretat municipal', 'La Diputació de Lleida presenta nous serveis.', 'https://diputaciolleida.cat/ca/actualitat/noticies/ciber', 'diputacions'), 'diputacions')
        self.assertEqual(news.classify('Barcelona digitalitza serveis', 'L’Ajuntament de Barcelona desplega els nous sistemes.', 'https://barcelona.cat/noticia/digital', 'municipis'), 'barcelona')

    def test_competitors_require_company_and_ict_and_classify_geography(self):
        self.assertIsNone(news.classify('Nou centre de negocis', 'Una empresa obre una oficina a Madrid.', 'https://example.org/article', 'competition-es'))
        self.assertEqual(news.classify('Seidor amplia els serveis cloud a Catalunya', '', 'https://seidor.com/ca/noticia', 'competition-world'), 'competition-cat')
        self.assertEqual(news.classify('Capgemini desarrolla nuevos servicios cloud en España', '', 'https://capgemini.com/news/noticia', 'competition-world'), 'competition-es')
        self.assertEqual(news.classify('Capgemini expands cloud technology services', '', 'https://capgemini.com/news/noticia', 'competition-world'), 'competition-world')
        self.assertIsNone(news.classify('Atos expands cloud technology services', '', 'https://atos.net/news/noticia', 'competition-world'))

    def test_priority_over_recency_and_dates_inside_bucket(self):
        gov = item(title='La Generalitat reforça la ciberseguretat dels serveis públics', bucket='generalitat', url='https://govern.cat/noticia/ciber', published='2026-09-15', summary='La Generalitat ha anunciat noves mesures de ciberseguretat per reforçar la protecció dels serveis públics digitals i millorar la coordinació entre els departaments del Govern.')
        older = item(title='El CTTI inicia un projecte de ciberseguretat', published='2026-07-01', url='https://ctti.gencat.cat/ca/detall/noticia/2026/07/projecte')
        result = news.merge_items([], [], [gov, older, item()], NOW)
        self.assertEqual([x['bucket'] for x in result], ['ctti', 'ctti', 'generalitat'])
        self.assertEqual(result[0]['published'], item()['published'])

    def test_ssrf_and_credentials_are_rejected(self):
        for url in ('file:///tmp/news', 'http://localhost/news', 'http://127.0.0.1/x', 'https://user:pw@example.org/x', 'http://169.254.169.254/', 'http://[::1]/', 'https://example.org:8080/x'):
            self.assertFalse(news.public_url(url), url)
        self.assertTrue(news.public_url('https://govern.cat/noticia/123'))

    def test_google_and_generic_dogc_are_not_article_links(self):
        for url, title in [('https://news.google.com/rss/articles/xyz', 'Notícia'), ('https://dogc.gencat.cat/ca/inici/', 'Diari Oficial'), ('https://dogc.gencat.cat/ca/document-del-dogc/?documentId=123', 'DOGC - Gencat')]:
            self.assertTrue(news.generic_page(url, title))

    def test_short_extract_not_title_or_navigation(self):
        summary = news.summarize(['Inici Notícies CTTI', 'Accepta totes les galetes del nostre portal per poder navegar i consultar totes les notícies i els serveis del centre.', BODY])
        self.assertIn('El CTTI ha presentat', summary)
        self.assertLessEqual(len(summary.split()), 24)

    def test_html_article_avoids_footer_and_navigation(self):
        raw = '<nav><p>' + ('Menú de serveis digitals ' * 12) + '</p></nav><main><p>' + BODY + '</p></main><footer><p>' + ('Política de privacitat ' * 20) + '</p></footer>'
        result = news.article_data(raw, 'https://ctti.gencat.cat/noticia/test')
        self.assertIn('El CTTI ha presentat', result['summary'])
        self.assertNotIn('Menú', result['body'])
        self.assertNotIn('Política', result['body'])

    def test_aoc_body_outside_main_beats_related_article_elements(self):
        # AOC's main element contains only the header; body paragraphs live in a
        # sibling div while the related cards use article elements.
        text = 'El repositori documental DESA’L del Consorci AOC ha superat els 400 milions de documents electrònics custodiats a les administracions públiques catalanes.'
        unrelated = 'L’AOC ha assolit una fita en matèria de ciberseguretat amb vint-i-dos serveis certificats segons l’Esquema Nacional de Seguretat i la normativa vigent.'
        raw = '<main class="single-blog__header"><h1>DESA’L</h1></main><div class="single-blog__content"><div class="entry-content"><div class="single-blog__content-main"><p>' + text + '</p></div></div></div><div class="single-blog__related"><article><p>' + unrelated + '</p></article></div>'
        result = news.article_data(raw, 'https://www.aoc.cat/blog/2026/desal/')
        self.assertIn('400 milions', result['summary'])
        self.assertNotIn('vint-i-dos', result['body'])

    def test_official_ctti_aem_dates_and_empty_anchor_labels(self):
        raw = '<meta name="publish-date" content="06/07/2026"><a href="/ca/detall/noticia/2026/07/trobada" aria-label="El CTTI presenta els projectes estratègics de l’any"><i></i></a>'
        self.assertEqual(news.article_data(raw, 'https://ctti.gencat.cat/ca/inici')['published'], '2026-07-06T00:00:00+00:00')
        candidates = news.listing_candidates(raw, 'https://ctti.gencat.cat/ca/inici', 'ctti')
        self.assertEqual(len(candidates), 1)
        self.assertIn('projectes estratègics', candidates[0]['title'])

    def test_canigo_uses_dated_news_slug_not_site_modified_time(self):
        data = news.article_data('<meta property="article:modified_time" content="2026-09-16"><p>' + BODY + '</p>', 'https://canigo.ctti.gencat.cat/noticies/2026-07-29-orquestrador/')
        self.assertEqual(data['published'], '2026-07-29T00:00:00+00:00')

    def test_json_ld_publication_date_not_modified(self):
        raw = '<script type="application/ld+json">' + json.dumps({'@type': 'NewsArticle', 'headline': 'Nous serveis', 'datePublished': '2026-07-02', 'dateModified': '2026-09-15', 'articleBody': BODY}) + '</script>'
        self.assertEqual(news.article_data(raw, 'https://example.org/story')['published'], '2026-07-02T00:00:00+00:00')

    def test_same_title_and_tracking_url_duplicates_removed(self):
        a = item(url=item()['url'] + '?utm_source=test')
        result = news.merge_items([], [], [item(), a], NOW)
        self.assertEqual(len(result), 1)
        self.assertNotIn('utm_', result[0]['url'])

    def test_reviewed_url_overrides_different_title_and_newer_automatic_date(self):
        automatic = item(title='Actualització obligatòria del sistema', published='2026-09-09', summaryKind='extractive')
        reviewed = item(title='Dues dates contradictòries en l’actualització del CTTI', published='2026-09-08', dateKind='updated')
        result = news.merge_items([], [automatic], [reviewed], NOW)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], reviewed['title'])
        self.assertEqual(result[0]['published'], '2026-09-08')
        self.assertEqual(result[0]['dateKind'], 'updated')

    def test_unrelated_consultancy_and_property_news_are_rejected(self):
        examples = [
            ('Businesses accelerate their climate adaptation investments', 'Climate disruption, water stress, resource constraints, and geopolitical volatility are increasing pressure on business operations, supply chains and growth.', 'competition-world'),
            ('The new era of private markets', 'For decades, private markets were reserved for large institutions and select ultra-high-net-worth individuals, constrained by commitments of at least one million dollars.', 'competition-world'),
            ('Life insurers under pressure', 'The life insurance industry is facing a relevance challenge as consumers become confused and unconvinced by policies available in the market.', 'competition-world'),
            ('El Govern i la UIB inicien les futures instal·lacions universitàries al ParcBit', 'El vicerector d’Economia, Infraestructures i Campus de la UIB ha formalitzat davant notari l’adquisició de la parcel·la 7A per construir noves instal·lacions.', 'balears')]
        for title, summary, bucket in examples:
            self.assertFalse(news.headline_ict(title, summary, bucket, 'https://capgemini.com/news/story'), title)
            cached = item(title=title, summary=summary, bucket=bucket, contentBucket=bucket, url='https://example.org/news/story')
            self.assertIsNone(news.validated_item(cached, now=NOW))

    def test_summary_prefers_actual_ict_information_over_anecdote(self):
        anecdote = 'Imagina’t la Laura. Va a l’ajuntament del seu poble a demanar un ajut social i fa deu anys hauria hagut de tornar a casa.'
        fact = 'El servei Via Oberta ha evitat milions de tràmits presencials mitjançant la consulta automatitzada de dades entre administracions públiques.'
        summary = news.summarize([anecdote, fact], 'La història de 21 milions de gestions invisibles')
        self.assertIn('Via Oberta', summary)
        self.assertNotIn('Laura', summary)

    def test_cutoff_day_and_sap_relevance(self):
        self.assertTrue(news.fresh('2026-03-20', 'diputacions', NOW.replace(hour=18)))
        self.assertTrue(news.headline_ict('SEIDOR alerta dels riscos als sistemes SAP', '', 'competition-es'))

    def test_offline_migration_does_not_fetch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / 'site/data'
            directory.mkdir(parents=True)
            (directory / 'news.json').write_text(json.dumps({'items': [item(summary='Old headline')]}), encoding='utf-8')
            (directory / 'news-reviewed.json').write_text(json.dumps({'items': [item()]}), encoding='utf-8')
            real_fresh = news.fresh
            with patch.object(news, 'ROOT', root), patch.dict('os.environ', {'NEWS_OFFLINE': '1'}), patch.object(news, 'get') as fetch, patch.object(news, 'fresh', side_effect=lambda p, b, now=None: real_fresh(p, b, now or NOW)):
                news.main()
            fetch.assert_not_called()
            result = json.loads((directory / 'news.json').read_text(encoding='utf-8'))
            self.assertEqual(result['version'], 2)
            self.assertEqual(len(result['items']), 1)
            self.assertIsNone(result['lastFetched'])

class MetaDataNewsTests(unittest.TestCase):
    URL = 'https://www.metadata.cat/noticia/9999/projecte-digital'
    TITLE = 'Una trobada del sector digital defineix prioritats compartides'
    SUBTITLE = ('Els participants han compartit propostes sobre serveis digitals i han '
                'analitzat les necessitats de modernització de diferents organitzacions '
                'durant una jornada oberta al sector tecnològic.')

    def setUp(self):
        real_fresh = news.fresh
        frozen = patch.object(news, 'fresh', side_effect=lambda p, b, now=None: real_fresh(p, b, now or NOW))
        frozen.start()
        self.addCleanup(frozen.stop)

    def article(self, body=BODY, outside=''):
        # MetaData puts the article text in this div and NewsArticle JSON-LD
        # after it; the publisher's other page blocks are not article content.
        structured = {'@context': 'http://schema.org', '@type': 'NewsArticle',
                      'headline': self.TITLE, 'datePublished': '2026-09-15T09:30:00+02:00',
                      'dateModified': '2026-09-16T11:00:00+02:00',
                      'publisher': {'@type': 'Organization', 'name': 'MetaData'}}
        return ('<html><head><link rel="canonical" href="' + self.URL + '"></head><body>'
                '<main><div class="interior-main__content"><p>' + body + '</p></div>'
                '<section class="other-stories"><p>' + outside + '</p></section></main>'
                '<script type="application/ld+json">' + json.dumps(structured) + '</script>'
                '</body></html>')

    def test_metadata_feed_is_mixed_scope_and_has_publisher_name(self):
        feed = 'https://www.metadata.cat/sindica'
        self.assertIn(('all', feed), news.FEEDS)
        raw = ('<rss version="2.0"><channel><title>MetaData</title><item>'
               '<title><![CDATA[' + self.TITLE + ']]></title><link>' + self.URL + '</link>'
               '<pubDate>Tue, 15 Sep 2026 09:30:00 +0200</pubDate>'
               '<description><![CDATA[<img src="https://www.metadata.cat/img/test.png">'
               + self.SUBTITLE + ']]></description></item></channel></rss>')
        rows = news.parse_feed(raw, 'all', feed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source'], 'MetaData')
        self.assertEqual(rows[0]['bucket'], 'all')
        self.assertEqual(rows[0]['published'], '2026-09-15T07:30:00+00:00')
        self.assertEqual(rows[0]['url'], self.URL)

    def test_metadata_reads_full_article_even_if_subtitle_can_be_summarized(self):
        self.assertTrue(news.summarize([self.SUBTITLE], self.TITLE))
        candidate = {'url': self.URL, 'title': self.TITLE, 'bucket': 'all',
                     'source': 'MetaData', 'content': self.SUBTITLE,
                     'published': '2026-09-16T08:00:00+00:00'}
        with patch.object(news, 'get', return_value=(self.article(), self.URL)) as fetch:
            result = news.make_item(candidate)
        fetch.assert_called_once_with(self.URL)
        self.assertIsNotNone(result)
        self.assertEqual(result['bucket'], 'ctti')
        self.assertEqual(result['source'], 'MetaData')
        self.assertEqual(result['summaryKind'], 'extractive')
        self.assertIn('El CTTI', result['summary'])
        self.assertNotIn('Els participants', result['summary'])
        self.assertEqual(result['published'], '2026-09-15T07:30:00+00:00')

    def test_metadata_content_selector_excludes_other_page_blocks(self):
        body = ('Una plataforma de programari lliure permet compartir eines digitals '
                'entre equips de recerca i automatitzar tasques repetitives sense '
                'dependre de serveis externs.')
        outside = ('El CTTI reforça la ciberseguretat dels sistemes públics amb una nova '
                   'estratègia que coordina els recursos i els serveis dels departaments.')
        result = news.article_data(self.article(body, outside), self.URL)
        self.assertIn('programari lliure', result['body'])
        self.assertNotIn('CTTI', result['body'])
        self.assertNotIn('CTTI', result['summary'])
        self.assertIsNone(news.classify(result['title'], result['body'], self.URL, 'all'))

    def test_metadata_json_ld_publication_offset_beats_modified_time(self):
        result = news.article_data(self.article(), self.URL)
        self.assertEqual(result['published'], '2026-09-15T07:30:00+00:00')
        self.assertEqual(news.parse_date(result['published']).utcoffset(), dt.timedelta(0))

    def test_metadata_ctti_mention_after_long_article_introduction(self):
        introduction = ('La jornada analitza com millorar els serveis digitals i coordinar '
                        'els projectes compartits entre equips de diferents institucions. ') * 45
        self.assertGreater(len(introduction), 4500)
        body = introduction + 'El CTTI ha participat en la definició del model de governança.'
        self.assertEqual(news.classify(self.TITLE, body, self.URL, 'all'), 'ctti')

    def test_metadata_does_not_confuse_other_transfer_centre_with_ctti(self):
        body = ('El Centre de Transferència de Tecnologia i Innovació (CTTI) presenta '
                'un nou programa de recerca digital amb equips universitaris.')
        self.assertIsNone(news.classify('Un centre universitari impulsa la recerca digital', body, self.URL, 'all'))

    def test_metadata_catalan_data_protection_authority_is_recognized(self):
        for authority in ('APDCAT', 'Autoritat Catalana de Protecció de Dades'):
            with self.subTest(authority=authority):
                body = ('La ' + authority + ' desenvolupa sistemes d’intel·ligència artificial '
                        'per automatitzar processos interns i gestionar les sol·licituds de ciutadania.')
                self.assertEqual(news.classify('Nous sistemes d’intel·ligència artificial', body, self.URL, 'all'), 'generalitat')

    def test_metadata_geography_or_central_government_does_not_imply_generalitat(self):
        generic = ('Una fira de software reuneix empreses emergents de Catalunya '
                   'per presentar eines digitals destinades a diferents sectors professionals.')
        central = ('El Govern central desplega serveis digitals per a empreses de Catalunya '
                   'dins un programa estatal de modernització dels sistemes informàtics.')
        for body in (generic, central):
            for requested in ('all', 'generalitat'):
                with self.subTest(body=body, requested=requested):
                    self.assertIsNone(news.classify('Un programa de serveis digitals', body, self.URL, requested))

    def test_metadata_ctti_search_discovers_original_article_once(self):
        raw = ('<a href="/noticia/9999/projecte-digital">El CTTI presenta nous projectes de serveis digitals</a>'
               '<a href="/noticia/9999/projecte-digital">El CTTI presenta nous projectes de serveis digitals</a>')
        rows = news.listing_candidates(raw, 'https://www.metadata.cat/cerca?que=CTTI', 'ctti')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source'], 'MetaData')
        self.assertEqual(rows[0]['url'], self.URL)

    def test_mixed_publisher_quota_does_not_consume_official_feed_slots(self):
        def candidates(bucket, domain, number, prefix):
            return [{'bucket': bucket, 'url': 'https://' + domain + '/noticia/' + prefix + str(i)} for i in range(number)]
        rows = (candidates('all', 'www.metadata.cat', 40, 'all-') +
                candidates('ctti', 'www.metadata.cat', 20, 'ctti-') +
                candidates('generalitat', 'www.aoc.cat', 10, 'gov-') +
                candidates('ctti', 'ctti.gencat.cat', 20, 'official-'))
        selected = news.select_candidates(rows)
        counts = {}
        for candidate in selected:
            key = (news.host(candidate['url']), candidate['bucket'])
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(counts[('metadata.cat', 'all')], 30)
        self.assertEqual(counts[('metadata.cat', 'ctti')], 12)
        self.assertEqual(counts[('aoc.cat', 'generalitat')], 6)
        self.assertEqual(counts[('ctti.gencat.cat', 'ctti')], 12)

    def test_mixed_discovery_deduplicates_tracking_urls_across_buckets(self):
        rows = [{'bucket': 'ctti', 'url': self.URL + '?utm_source=search'},
                {'bucket': 'all', 'url': self.URL + '?utm_source=rss'},
                {'bucket': 'all', 'url': self.URL + '-other'}]
        selected = news.select_candidates(rows)
        canonical = [news.original_url(candidate['url']) for candidate in selected]
        self.assertEqual(canonical, [self.URL, self.URL + '-other'])


if __name__ == '__main__':
    unittest.main()
