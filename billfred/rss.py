import feedparser
import logging

logger = logging.getLogger(__name__)


last_dates = {}


def process_feed(prefix, url):
    """Download feed and return new entries."""
    logger.info('Downloading RSS %s %s', prefix, url)
    feed = feedparser.parse(url)
    # Check errors
    if feed.bozo:
        logger.error('Feed %s error: %s', prefix, feed.bozo_exception)
        return

    last_date = last_dates.get(prefix)
    # First run - do nothing but save last seen entry date
    if last_date is None:
        if len(feed.entries):
            last_dates[prefix] = max([e.published_parsed for e in feed.entries])
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
        entries.append('{}: {} {}'.format(prefix, entry.title, entry.link))

    last_dates[prefix] = max_date
    logger.info('RSS %s processed, %s new entries', prefix, len(entries))
    return entries


def rss_thread(queue_in, queue_out):
    """Thread for RSS, receives (prefix, url) and returns entries."""
    while True:
        try:
            msg = queue_in.get()
            # Stop thread when 'stop' received
            if msg == 'stop':
                break
            entries = process_feed(*msg)
            if entries:
                queue_out.put({'message': '\n'.join(entries)})
        except Exception as e:
            logger.exception('Feed thread error')
