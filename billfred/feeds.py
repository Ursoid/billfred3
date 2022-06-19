import asyncio
import feedparser
import logging
from io import StringIO
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

last_dates = {}


class TagsStripper(HTMLParser):
    """Simple tags stripper for html content."""

    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        """Write into local cache."""
        self.text.write(d)

    def get_data(self):
        """Get cleaned contents."""
        return self.text.getvalue()


def strip_html(data):
    """Try to transform html to text."""
    stripper = TagsStripper()
    stripper.feed(data)
    return stripper.get_data()


def process_feed(prefix, url, show_body=False):
    """Download feed and return new entries."""
    logger.info('Downloading feed %s %s', prefix, url)
    feed = feedparser.parse(url)
    # Check errors
    if feed.bozo:
        logger.error('Feed %s error: %s', prefix, feed.bozo_exception)
        return

    last_date = last_dates.get(prefix)
    # First run - do nothing but save last seen entry date
    if last_date is None:
        if len(feed.entries):
            last_dates[prefix] = max([
                e.published_parsed for e in feed.entries
            ])
        else:
            logger.info('No entries in %s %s', prefix, url)
        return

    max_date = last_date
    entries = []
    for entry in feed.entries:
        if entry.published_parsed <= last_date:
            continue
        if entry.published_parsed > max_date:
            max_date = entry.published_parsed
        result = '{}: {} {}'.format(prefix, entry.title, entry.link)
        if show_body:
            content = []
            if entry.get('summary') and entry.get('summary_detail'):
                text = entry.summary
                if entry.summary_detail['type'] == 'text/html':
                    text = strip_html(text)
                content.append(text)
            if 'content' in entry:
                for i in entry.content:
                    text = i.get('value')
                    if i.get('type') == 'text/html':
                        text = strip_html(text)
                    content.append(text)
            if content:
                result += '\n\n{}\n'.format('\n'.join(content))
        entries.append(result)

    last_dates[prefix] = max_date
    logger.info('Feed %s processed, %s new entries', prefix, len(entries))
    return entries


async def feed_checker(client, task):
    """Run periodic feed check."""
    while True:
        try:
            loop = asyncio.get_running_loop()
            entries = await loop.run_in_executor(
                client.feed_pool, process_feed,
                task['prefix'], task['url'], task['show_body']
            )
            if entries:
                client.send_bot_message({'message': '\n'.join(entries)})
        except Exception:
            logger.exception('Feed thread error')
        await asyncio.sleep(task['time'])
