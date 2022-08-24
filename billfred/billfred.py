import slixmpp
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from slixmpp.exceptions import XMPPError, IqError, IqTimeout

from billfred.database import Database
from billfred.links import Links
from billfred.wiki import Wiki
from billfred.eliza import ask_eliza
from billfred.feeds import feed_checker

logger = logging.getLogger(__name__)

BOT_VERSION = 0.2

HELP_TEXT = r'''Billfred bot, version: {}
Writes chat log and displays URL title if available.
Bot commands:
  ping -- ping user
  help -- display this text
  wiki -- find wikipedia articles. Usage:
          wiki(lang)(:title)
            lang -- wiki language
            :title - search only in title
          Examples:
            wiki QUERY -- search ru wiki
            wikien QUERY -- search en wiki
            wiki:title QUERY -- search ru wiki in title
            wikies:title QUERY -- search es wiki in title
  (any other text) -- ask Eliza
'''.format(BOT_VERSION)


class Billfred(slixmpp.ClientXMPP):
    """Billfred chat bot."""
    reconnect_timeout = 10

    def __init__(self, config):
        self.config = config
        jid = config['account']['jid']
        password = config['account']['password']
        super().__init__(jid, password)

        self.room = config['account']['room']
        self.nick = config['account']['nick']

        # Load modules
        self.register_plugin('xep_0045')  # Multi-User Chat
        self.register_plugin('xep_0199')  # XMPP Ping

        # Initialize subsystems
        db_path = '{}_chatlog.db'.format(self.room)
        if 'database' in config and config['database'].get('database_path'):
            db_path = config['database']['database_path']
        self.db = Database(db_path)
        self.links = Links(self)
        self.wiki = Wiki(self)
        self.eliza_pool = ThreadPoolExecutor(max_workers=5)

        self.add_event_handler("session_start", self.start)
        # Maybe move it to top level destructor?
        self.add_event_handler("session_end", self.stop)
        self.add_event_handler("groupchat_message", self.muc_message)
        self.add_event_handler("send_bot_message", self.send_bot_message)

    async def start(self, event):
        """Initialize async services and connect."""
        await self.db.init()
        self.init_feeds()
        try:
            await self.get_roster()
            self.send_presence()
            # FIXME password
            logger.info('Joining MUC')
            await self.plugin['xep_0045'].join_muc_wait(self.room,
                                                        self.nick,
                                                        timeout=10)
            logger.info('Connected to %s as %s', self.room, self.nick)
        except XMPPError as e:
            logger.exception('Error on MUC join: %s', e)
            self.disconnect()
            return

    async def stop(self, *args, **kwargs):
        """Stop all async services."""
        logger.info('Stopping service')
        try:
            await self.links.close()
            await self.wiki.close()
            await self.db.close()
            for task in self.feed_tasks:
                task.cancel()
            self.disconnect()
        except Exception:
            logger.exception('Error on stopping')
        if not self.config['account'].getboolean('no_reconnect'):
            logger.info('Reconnecting after %s seconds', self.reconnect_timeout)
            await asyncio.sleep(self.reconnect_timeout)
            self.connect()

    async def log_exception(self, func):
        """Log exception from async tasks."""
        try:
            return await func
        except Exception:
            logger.exception("Unhandled exception")

    def create_task(self, func):
        """Wrapper for running async task with exception logging."""
        return asyncio.create_task(self.log_exception(func))

    def init_feeds(self):
        """Initialize feed checker and start initial run."""
        logger.info('Initializing feeds')
        self.feed_pool = ThreadPoolExecutor(max_workers=5)
        self.feed_tasks = []
        for section in self.config.sections():
            if section.startswith('rss_'):
                task = {
                    'prefix': self.config[section]['prefix'],
                    'url': self.config[section]['url'],
                    'time': int(self.config[section]['time']),
                    'show_body': self.config[section].getboolean(
                        'show_body', True
                    )
                }
                logger.info('Adding feed %s', task['url'])
                self.feed_tasks.append(
                    self.create_task(feed_checker(self, task))
                )
        logger.info('Finished feeds initialization')

    def send_bot_message(self, data):
        """Send message from bot."""
        try:
            self.send_message(mto=data.get('to', self.room),
                              mbody=data['message'],
                              mtype='groupchat')
        except IqError as e:
            logger.info("Error sending message to %s: %s",
                        data['to'],
                        e.iq['error']['condition'])
        except IqTimeout:
            logger.info("No response from %s", data['to'])
        except Exception:
            logger.exception("Error on message send")

    def muc_message(self, msg):
        """Process message and do actions depending on its content."""
        message = msg['body']   # Message body

        # Write message to database
        self.create_task(self.db.write(msg))

        # Disable self-interaction
        if msg['mucnick'] == self.nick:
            return

        # Link title parser
        if (
                not self.links.disabled and
                'http' in message and
                not self.links.is_ignored(msg['mucnick'])
        ):
            links = Links.extract_links(message)
            self.create_task(
                self.links.process(
                    [{
                        'to': msg['from'].bare,
                        'link': link
                    } for link in links[:self.links.links_limit]]
                )
            )

        # Bot command parser
        if msg['body'].startswith(self.nick):

            tokens = msg['body'].split()
            if len(tokens) > 1:
                command = tokens[1]

            # Ping command
            if command == 'ping':
                self.create_task(self.try_ping(msg['from'], msg['mucnick']))
            elif command == 'version':
                self.send_bot_message({
                    'to': msg['from'].bare,
                    'message': "Bot version: {}".format(BOT_VERSION)
                })
            elif command == 'help':
                self.send_bot_message({
                    'to': msg['from'].bare,
                    'message': HELP_TEXT
                })
            elif command.startswith('wiki'):
                query, lang, in_title = self.wiki.parse_command(msg['body'])
                if query is not None:
                    self.create_task(self.wiki.search(query, lang, in_title))
            else:
                self.create_task(ask_eliza(
                    self,
                    msg['from'].bare,
                    ' '.join(tokens[1:])
                ))

    async def try_ping(self, pingjid, nick):
        """Ping user."""
        logger.debug('Got ping from nick "%s" jid "%s"', nick, pingjid)
        try:
            rtt = await self['xep_0199'].ping(pingjid, timeout=10)
            self.send_message(mto=pingjid.bare,
                              mbody="%s, pong is: %s" % (nick, rtt),
                              mtype='groupchat')
            logger.debug('Successfully pinged %s (%s)', nick, pingjid)
        except IqError as e:
            logger.info("Error pinging %s: %s",
                        pingjid,
                        e.iq['error']['condition'])
        except IqTimeout:
            logger.info("No response from %s", pingjid)
