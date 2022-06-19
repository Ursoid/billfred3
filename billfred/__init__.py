import sys
import logging
import logging.config
import argparse
import configparser

from billfred.billfred import Billfred


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
    if not any([jid, password, room, nick]):
        logger.error('Wrong account parameters, exiting')
        sys.exit('Config error')

    xmpp = Billfred(config)

    # Connect to the XMPP server and start processing XMPP stanzas.
    try:
        xmpp.connect()
        xmpp.process(forever=True)
    except KeyboardInterrupt:
        logger.info('Disconnecting')
        xmpp.disconnect()
    except Exception:
        logger.exception('Error')
    logger.info('Done')


if __name__ == '__main__':
    main()
