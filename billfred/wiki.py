import asyncio
import logging
import aiohttp
from urllib.parse import urlencode, quote


logger = logging.getLogger(__name__)


class Wiki:
    """Search wikipedia for articles."""
    BASE_URL = 'https://{lang}.wikipedia.org{query}'
    API_INTERVAL = 2
    DEFAULT_LANG = 'ru'
    ARTICLES_LIMIT = 3

    def __init__(self, client):
        self.client = client
        self.session = aiohttp.ClientSession()

    async def close(self):
        """Destroy session."""
        if self.session:
            logger.info('Destroying links session')
            await self.session.close()

    def api_url(self, query, lang):
        """Get API url for specified language"""
        q = '/w/api.php?{}'.format(urlencode(query))
        return self.BASE_URL.format(lang=lang, query=q)

    def page_url(self, page, lang):
        """Get API url for specified language"""
        q = '/wiki/{}'.format(quote(page))
        return self.BASE_URL.format(lang=lang, query=q)

    def format_snippet(self, text):
        """Transform tags from snippet to something that can be displayed."""
        if text:
            text = text.\
                replace('<span class="searchmatch">', '_').\
                replace('</span>', '_')
        return text

    def parse_command(self, message):
        """Parse wiki command arguments."""
        tokens = message.split()
        if len(tokens) < 2:
            return None, None, None
        command = tokens[1]
        cmd = command.split(':')
        lang = cmd[0][len('wiki'):] or None
        if lang is None:
            lang = self.DEFAULT_LANG
        in_title = len(cmd) > 1 and cmd[1] == 'title'
        query = ' '.join(tokens[2:])
        return query, lang, in_title

    async def search(self, text, lang, only_title=True):
        """Ask Wikipedia about something. Don't ask about bad things!"""
        logger.info('Searching wiki %s %s %s', text, lang, only_title)
        q = {
            'action': 'query',
            'list': 'search',
            'format': 'json',
            'srsearch': 'intitle:{}'.format(text) if only_title else text,
            'srnamespace': 0,
            'srprop': 'snippet',
            'srlimit': self.ARTICLES_LIMIT,
        }
        url = self.api_url(q, lang)
        error = False
        result = []
        try:
            logger.info('Querying %s', url)
            async with self.session.get(url) as r:
                response = await r.json()
            if not response.get('query', {}).get('search'):
                logger.warning("Response doesn't contain results: %s",
                               response)
                error = True
            else:
                for item in response['query']['search']:
                    link = self.page_url(item['title'], lang)
                    snippet = self.format_snippet(item.get('snippet'))
                    text = '{} - *{}*: {}'.format(link,
                                                  item.get('title'),
                                                  snippet)
                    result.append(text)
        except aiohttp.ClientError as e:
            logger.error('Net error: %s', e)
            error = True
        except Exception as e:
            logger.exception("Unhandled exception: %s", e)
            error = True

        if error:
            result = ['Search error']
        if not result:
            result = ['Nothing found, sorry']

        self.client.send_bot_message({
            'message': '\n\n'.join(result)
        })

        await asyncio.sleep(self.API_INTERVAL)
