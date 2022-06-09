#!/usr/bin/env python
import sys
import ssl
import queue
import threading
import logging
import logging.config
import argparse
import configparser
import ssl

from billfred.billfred import Billfred
# from billfred.database import db_thread
# from billfred.links import links_thread
# from billfred.rss import rss_thread
# from billfred.wiki import wiki_thread


logger = logging.getLogger(__name__)


def main():
    """Main function that launches bot."""
    parser = argparse.ArgumentParser(description='A jabber bot.')
    parser.add_argument(
        '--config',
        default='billfred.cfg',
        help='path to config file'
    )
    args = parser.parse_args()

    # Load config file 
    config = configparser.ConfigParser()
    config.read(args.config)

    # Setup logging.
    logging.config.fileConfig(args.config)

    jid = config['account']['jid']
    password = config['account']['password']
    room = config['account']['room']
    nick = config['account']['nick']
    if not any([jid, password, room]):
        logger.error('Wrong account parameters, exiting')
        sys.exit(78)

    # RSS tasks
    rss_tasks = []
    for section in config.sections():
        if section.startswith('rss_'):
            rss_tasks.append([
                config[section]['prefix'],
                config[section]['url'],
                int(config[section]['time'])
            ])

    # db_queue = queue.Queue()
    # to_links = queue.Queue()
    # to_rss = queue.Queue()
    # to_wiki = queue.Queue()
    # msg_q = queue.Queue()
    xmpp = Billfred(config)
    # jid, password, room, nick
    # xmpp.ssl_version = ssl.PROTOCOL_TLSv1_2

    # Start thread for logging
    # db_thr = threading.Thread(target=db_thread, args=(db_path, db_queue))
    # db_thr.start()

    # # Start links parser thread
    # links_thr = threading.Thread(target=links_thread, args=(to_links, msg_q))
    # links_thr.start()

    # # Start RSS feed downloader thread
    # rss_thr = threading.Thread(target=rss_thread, args=(to_rss, msg_q))
    # rss_thr.start()

    # # Start WIKI thread
    # wiki_thr = threading.Thread(target=wiki_thread, args=(to_wiki, msg_q))
    # wiki_thr.start()

    # Connect to the XMPP server and start processing XMPP stanzas.
    try:
        xmpp.connect()
        xmpp.process(forever=True)
    except Exception:
        logger.exception('Error on xmpp connect')
    finally:
        # Always close threads
        pass
        # [q.put('stop') for q in (db_queue, to_links, to_rss)]
        # db_thr.join()
    # SIGNAL fixme
    logger.info('Done')


if __name__ == '__main__':
    main()
