import sys
import queue
import threading
import logging
import logging.config
import argparse
import configparser

from billfred.billfred import Billfred
from billfred.database import db_thread


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
    
    # Database
    db_path = config['database']['database_path']
    if not db_path:
        db_path = '{}_chatlog.db'.format(room)

    db_queue = queue.Queue()
    xmpp = Billfred(jid, password, room, nick, db_queue)

    # Start thread for logging
    db_thr = threading.Thread(target=db_thread, args=(db_path, db_queue))
    db_thr.start()

    # Connect to the XMPP server and start processing XMPP stanzas.
    try:
        if xmpp.connect():
            xmpp.process(block=True)
        else:
            logger.error('Unable to connect')
    finally:
        # Always close db thread
        db_queue.put('stop')
        db_thr.join()
    logger.info('Done')


if __name__ == '__main__':
    main()
