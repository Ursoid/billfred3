import sys
import queue
import threading
import logging
import logging.config
import argparse
import configparser

from billfred.billfred import Billfred
from billfred.database import db_thread
from billfred.links import links_thread
from billfred.rss import rss_thread


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

    jid = config['account']['jid'].strip()
    password = config['account']['password'].strip()

    if not any([jid, password]):
        logger.error('Wrong account parameters, exiting')
        sys.exit(78)

    # Get all rooms
    rooms = {}
    for section in config.sections():
        if section.startswith('room_'):
            # Add an account
            name = section.replace('room_', '')
            rooms[name] = {}
            for key in (('room', 'password', 'nick')):
                rooms[name][key] = config[section][key]

    # Get all RSS feeds. Doing it after rooms check because feed
    # references room.
    rss_tasks = []
    for section in config.sections():
        if section.startswith('rss_'):
            # Add RSS task
            room_names = [r.strip() for r in config[section]['rooms'].split(',')]
            room_jids = [rooms[name]['room']
                         for name in room_names if name in rooms]
            rss_tasks.append({
                'prefix': config[section]['prefix'],
                'url': config[section]['url'],
                'rooms': room_jids,
                'time': config.getint(section, 'time')
            })

    # Database
    db_path = config['database']['database_path']
    if not db_path:
        db_path = 'billfred_chatlog.db'

    db_queue = queue.Queue()
    to_links = queue.Queue()
    to_rss = queue.Queue()
    msg_q = queue.Queue()
    xmpp = Billfred(jid, password, rooms, rss_tasks, db_queue,
                    to_links, to_rss, msg_q)

    # Start thread for logging
    db_thr = threading.Thread(target=db_thread, args=(db_path, db_queue))
    db_thr.start()

    # Start links parser thread
    links_thr = threading.Thread(target=links_thread, args=(to_links, msg_q))
    links_thr.start()

    # Start RSS feed downloader thread
    rss_thr = threading.Thread(target=rss_thread, args=(to_rss, msg_q))
    rss_thr.start()

    # Connect to the XMPP server and start processing XMPP stanzas.
    try:
        if xmpp.connect():
            xmpp.process(block=True)
        else:
            logger.error('Unable to connect')
    except Exception as e:
        logger.exception('Error on xmpp connect')
    finally:
        # Always close threads
        [q.put('stop') for q in (db_queue, to_links, to_rss)]
        db_thr.join()
    logger.info('Done')


if __name__ == '__main__':
    main()
