import asyncio
import feedparser
import logging

logger = logging.getLogger(__name__)

last_dates = {}


def process_feed(prefix, url):
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
        entries.append('{}: {} {}'.format(prefix, entry.title, entry.link))

    last_dates[prefix] = max_date
    logger.info('Feed %s processed, %s new entries', prefix, len(entries))
    return entries


async def feed_checker(client, task):
    """Run periodic feed check."""
    while True:
        try:
            loop = asyncio.get_running_loop()
            entries = await loop.run_in_executor(
                client.feed_pool, process_feed, task['prefix'], task['url']
            )
            if entries:
                client.send_bot_message({'message': '\n'.join(entries)})
        except Exception:
            logger.exception('Feed thread error')
        await asyncio.sleep(task['time'])
