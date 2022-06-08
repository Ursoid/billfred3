import json
import time
import logging
from urllib.request import urlopen
from urllib.parse import urlencode, quote


logger = logging.getLogger(__name__)

BASE_URL = 'https://{lang}.wikipedia.org{query}'
API_INTERVAL = 2
DEFAULT_LANG = 'ru'


def api_url(query, lang):
    """Get API url for specified language"""
    q = '/w/api.php?{}'.format(urlencode(query))
    return BASE_URL.format(lang=lang, query=q)


def page_url(page, lang):
    """Get API url for specified language"""
    q = '/wiki/{}'.format(quote(page))
    return BASE_URL.format(lang=lang, query=q)

def format_snippet(text):
    """Transform tags from snippet to something that can be displayed."""
    if text:
        text = text.\
            replace('<span class="searchmatch">', '_').replace('</span>', '_')
    return text


def search_wiki(text, lang, only_title=True):
    """Ask Wikipedia about something. Don't ask about bad things!"""
    q = {
        'action': 'query',
        'list': 'search',
        'format': 'json',
        'srsearch': 'intitle:{}'.format(text) if only_title else text,
        'srnamespace': 0,
        'srprop': 'snippet',
        'srlimit': 3,
    }
    url = api_url(q, lang)
    result = []
    try:
        logger.info('Querying %s', url)
        with urlopen(url) as r:
            data = r.read()
        response = json.loads(data.decode('utf-8'))
        if not response.get('query', {}).get('search'):
            logger.warning("Response doesn't contain results: %s", response)
            return False

        for item in response['query']['search']:
            link = page_url(item['title'], lang)
            snippet = format_snippet(item.get('snippet'))
            text = '{} - *{}*: {}'.format(link, item.get('title'), snippet)
            result.append(text)
    except Exception as e:
        logger.exception("Unhandled exception: %s", e)
        return

    if not result:
        result = ['Nothing found, sorry']
    
    return result


def wiki_thread(queue_in, queue_out):
    """Thread for wiki API queries."""
    while True:
        query = queue_in.get()
        # Stop thread when 'stop' received
        if query == 'stop':
            break
        if not isinstance(query, dict) or not all(
                k in query for k in ['to', 'lang', 'query', 'in_title']
        ):
            continue
        lang = query['lang']
        if not lang:
            lang = DEFAULT_LANG
        logger.info('Querying wiki, lang: %s in_title: %s query: "%s"',
                    lang, query['in_title'], query['query'])
        results = search_wiki(query['query'], lang, query['in_title'])
        if results is None:
            message = 'Error'
        elif results is False:
            message = 'Found nothing'
        else:
            message = '\n\n'.join(results)
        queue_out.put({'to': query['to'],
                       'message': message})
        # Just sleep for some time to reduce load
        time.sleep(API_INTERVAL)
