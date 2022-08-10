import asyncio
import aiohttp
import codecs
import cgi
import logging
import re
from charset_normalizer import detect
from urllib.parse import urlsplit
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


class TitleParser(HTMLParser):
    """HTML parser that extracts titles from page."""

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.domain = url.netloc
        self.title = None
        self.in_title = False
        self.title_buf = []

    def get_title(self):
        """Return title if ready."""
        return self.title

    def handle_starttag(self, tag, attrs):
        """Handle start of title tag."""
        if tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        """Handle end of title tag."""
        if tag == 'title':
            self.in_title = False
            self.title = ''.join(self.title_buf)

    def handle_data(self, data):
        """Append data to title buffer."""
        if self.in_title:
            self.title_buf.append(data)


class Links:
    """Service for getting titles from links."""
    EXT_BLACKLIST = (
        'png', 'jpg', 'jpeg', 'gif', 'png', 'pdf', 'doc', 'xls',
        'docx', 'djvu', 'ppt', 'pptx', 'avi', 'mp4', 'mp3', 'flac', 'pps',
        'mp3', 'ogg', 'webm', 'js', 'css'
    )
    ALLOWED_TYPES = ('text/html', 'application/xhtml+xml')
    TOO_LONG = 1024 * 1024 * 5
    LINK_INTERVAL = 3
    LINK_RE = re.compile(r'https?://[^\s]+')
    CHUNK_SIZE = 1024
    LINKS_LIMIT = 3

    def __init__(self, client):
        self.client = client
        self.session = aiohttp.ClientSession()
        self.link_interval = self.LINK_INTERVAL
        self.links_limit = self.LINKS_LIMIT
        self.disabled = False
        conf = client.config
        if 'links' in conf:
            c = conf['links']
            if c.get('interval') is not None:
                self.link_interval = int(c['interval'])
            if c.get('limit') is not None:
                self.links_limit = int(c['limit'])
            if c.get('disabled'):
                self.disabled = c.getboolean('disabled')

    async def close(self):
        """Destroy session."""
        if self.session:
            logger.info('Destroying links session')
            await self.session.close()

    @classmethod
    def extract_links(cls, message):
        """Extract links from message."""
        return list(set(cls.LINK_RE.findall(message)))

    async def process(self, links):
        if self.disabled:
            return
        for link in links:
            logger.info('Processing link: %s', link['link'])
            title = await self.get_title(link['link'])
            if title is not None:
                self.client.send_bot_message({
                    'to': link['to'],
                    'message': 'TITLE: {}'.format(title)
                })
            if len(links) > 1:
                await asyncio.sleep(self.link_interval)
        # Just sleep for some time to reduce load
        await asyncio.sleep(self.link_interval)

    def is_allowed(self, url):
        """Check if url isn't blacklisted."""
        parsed_url = urlsplit(url.lower())
        return parsed_url.path.split('.')[-1] not in self.EXT_BLACKLIST

    def get_decoder(self, charset):
        """Get incremental decoder for specified charset."""
        cls = codecs.getincrementaldecoder(charset)
        return cls(errors='ignore')

    async def extract_title(self, response):
        """Extract title from response."""
        parsed_url = urlsplit(str(response.url).lower())
        title = None
        parser = TitleParser(parsed_url)
        charset = response.charset
        decoder = None
        if charset is not None:
            decoder = self.get_decoder(charset)
        async for chunk in response.content.iter_chunked(self.CHUNK_SIZE):
            if not decoder:
                detected = detect(chunk)
                if detected['encoding'] is not None:
                    decoder = self.get_decoder(detected['encoding'])
            if not decoder:
                # that page is hopeless
                logger.info('Can not detect charset')
                break
            parser.feed(decoder.decode(chunk))
            title = parser.get_title()
            if title is not None:
                break
        if title is not None:
            return title.strip()

    async def get_title(self, url):
        if not self.is_allowed(url):
            logger.debug('Not allowed extension: %s', url)
            return
        try:
            async with self.session.get(url) as r:
                # Check mimetype and size
                if int(
                        r.headers.get('content-length', self.TOO_LONG)
                ) > self.TOO_LONG:
                    logger.debug('Content too large: %s', url)
                    return
                mimetype, _ = cgi.parse_header(r.headers.get('content-type', ''))
                if mimetype not in self.ALLOWED_TYPES:
                    logger.debug('Not allowed: %s, %s', url, mimetype)
                    return
                title = await self.extract_title(r)
                if title:
                    logger.info('Found title: %s, %s', url, title)
                    return title
        except aiohttp.ClientError as e:
            logger.debug('Net error: %s', e)
        logger.debug('Title not found: %s', url)
