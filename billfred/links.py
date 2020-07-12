import requests
import cgi
import logging
import time
import re
from urllib.parse import urlsplit
from lxml.html import fromstring

logger = logging.getLogger(__name__)

EXT_BLACKLIST = (
    'png', 'jpg', 'jpeg', 'gif', 'png', 'pdf', 'doc', 'xls',
    'docx', 'djvu', 'ppt', 'pptx', 'avi', 'mp4', 'mp3', 'flac', 'pps',
    'mp3', 'ogg', 'webm', 'js', 'css'
)
ALLOWED_TYPES = ('text/html', 'application/xhtml+xml')
TOO_LONG = 1024 * 1024 * 5
LINK_INTERVAL = 3
LINK_RE = re.compile(r'https?://[^\s]+')


def is_allowed(url):
    """Check if url isn't blacklisted."""
    parsed_url = urlsplit(url.lower())
    return parsed_url.path.split('.')[-1] not in EXT_BLACKLIST


def extract_title(url, data):
    """Extract title from site content for specific url."""
    parsed_url = urlsplit(url.lower())
    tree = fromstring(data)
    title = None
    if ('youtube.com' in parsed_url.netloc or
        'youtu.be' in parsed_url.netloc):
        title = tree.xpath('//meta[@name="title"]/@content')
        if title:
            return '{} - YouTube'.format(title[0].strip())
    else:
        title = tree.xpath('//title/text()')
        if title:
            return title[0].strip()


def get_title(url):
    """Download page and get document title."""
    if not is_allowed(url):
        logger.debug('Not allowed extension: %s', url)
        return
    r = None
    try:
        r = requests.get(url, timeout=20, stream=True)
        if int(r.headers.get('content-length', TOO_LONG)) > TOO_LONG:
            logger.debug('Content too large: %s', url)
            return
        mimetype, _ = cgi.parse_header(r.headers.get('content-type', ''))
        if mimetype not in ALLOWED_TYPES:
            logger.debug('Not allowed: %s, %s', url, mimetype)
            return
        if (r.text.lstrip().startswith('<?xml') or
            'charset' not in r.headers.get('content-type')):
            data = r.content
        else:
            data = r.text
        title = extract_title(r.url, data)
        if title:
            logger.info('Found title: %s, %s', url, title)
            return title
        logger.debug('Title not found: %s', url)
    except requests.exceptions.RequestException as e:
        logger.debug('Error: %s', e)
    except Exception as e:
        logger.exception('Unhandled exception: %s', e)
    finally:
        if r is not None:
            r.close()


def links_thread(queue_in, queue_out):
    """Thread for link parser."""
    while True:
        links = queue_in.get()
        # Stop thread when 'stop' received
        if links == 'stop':
            break
        for link in links:
            logger.info('Processing link: %s', link['link'])
            title = get_title(link['link'])
            if title is not None:
                queue_out.put({'to': link['to'],
                               'message': 'TITLE: {}'.format(title)})
            if len(links) > 1:
                time.sleep(LINK_INTERVAL)
        # Just sleep for some time to reduce load
        time.sleep(LINK_INTERVAL)


def extract_links(message):
    """Extract links from message."""
    return list(set(LINK_RE.findall(message)))
