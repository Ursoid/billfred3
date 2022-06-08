import slixmpp
import time
import logging
import asyncio
# import queue
from slixmpp.exceptions import XMPPError, IqError, IqTimeout

from billfred.links import extract_links
from billfred.eliza import analyze

logger = logging.getLogger(__name__)

BOT_VERSION = 0.2


class Billfred(slixmpp.ClientXMPP):
    """Billfred chat bot."""
    # Amount of processed links in one message
    links_limit = 3

    def __init__(self, jid, password, room, nick):
        super().__init__(jid, password)

        # Load modules
        self.register_plugin('xep_0045')  # Multi-User Chat
        self.register_plugin('xep_0199')  # XMPP Ping

        self.room = room
        self.nick = nick
        self.add_event_handler("session_start", self.start)
        self.add_event_handler("groupchat_message", self.muc_message)
        self.add_event_handler("send_bot_message", self.send_bot_message)

    async def start(self, event):
        try:
            await self.get_roster()
            self.send_presence()
            # FIXME password
            await self.plugin['xep_0045'].join_muc(self.room,
                                                   self.nick)
            logger.info('Connected to %s as %s', self.room, self.nick)
        except XMPPError as e:
            logger.exception('Error on MUC join: %s', e)
            self.disconnect()
            return

    def check_rss(self, prefix, url):
        """Return function that will put RSS check task."""
        def do_check():
            self.to_rss.put((prefix, url))
        return do_check

    def check_messages(self):
        """Check if new messages from threads are available."""
        try:
            msg = self.msg_queue.get_nowait()
            if msg:
                self.event("send_bot_message", {
                    'to': msg.get('to', self.room),
                    'message': msg['message']
                })
        except queue.Empty:
            pass

    def send_bot_message(self, data):
        """Send message from bot."""
        try:
            self.send_message(mto=data['to'],
                              mbody=data['message'],
                              mtype='groupchat')
        except IqError as e:
            logger.info("Error sending message to %s: %s",
                        data['to'],
                        e.iq['error']['condition'])
        except IqTimeout:
            logger.info("No response from %s", data['to'])


    def muc_message(self, msg):
        """Process message and do actions depending on its content."""
        nick = msg['mucnick']   # User nick sowed in chat room
        jid = str(msg['from'])  # ful JID Like user@jabb.en/UserName
        message = msg['body']   # Message body
        time_local = time.time()
        # self.write_chat_log((time_local, jid, nick, message,))
        
        # Disable self-interaction
        if msg['mucnick'] == self.nick:
            return

        # Link title parser
        if 'http' in message:
            links = extract_links(message)
            self.to_links_queue.put([
                {'to': msg['from'].bare, 'link': l}
                for l in links[:self.links_limit]
            ])

        # Bot command parser
        if msg['body'].startswith(self.nick):

            tokens = msg['body'].split()
            if len(tokens) > 1:
                command = tokens[1]
               
            # Ping command
            if command == 'ping':
                asyncio.create_task(self.try_ping(msg['from'], msg['mucnick']))
            elif command == 'version':
                self.send_bot_message({
                    'to': msg['from'].bare,
                    'message': "Bot version: {}".format(BOT_VERSION)
                })
            elif command == 'test':
                self.send_bot_message({
                    'to': msg['from'].bare,
                    'message': "Custom command test. Bot version: {}".format(BOT_VERSION)
                })
            elif command.startswith('wiki'):
                # 'wiki' or 'wiki{lang}' with optional ':title'
                # examples: wiki query, wikiru query, wikiru:title query
                cmd = command.split(':')
                lang = cmd[0][len('wiki'):] or None
                in_title = len(cmd) > 1 and cmd[1] == 'title'
                self.to_wiki_queue.put({
                    'to': msg['from'].bare,
                    'query': ''.join(tokens[2:]),
                    'lang': lang,
                    'in_title': in_title
                })
            else:
                self.send_bot_message({
                    'to': msg['from'].bare,
                    'message': analyze(msg['body'])
                })

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

    def write_chat_log(self, query):
        """Send chat message to database writer thread."""
        self.db_queue.put(query)
