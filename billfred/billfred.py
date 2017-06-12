#!/usr/bin/env python
import sleekxmpp
import time
import logging
import queue

from billfred.links import extract_links

logger = logging.getLogger(__name__)

BOT_VERSION = 0.1


class Billfred(sleekxmpp.ClientXMPP):
    """Billfred chat bot."""
    # Amount of processed links in one message
    links_limit = 3

    def __init__(self, jid, password, room, nick, db_queue,
                 to_links_queue, from_links_queue):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        # Load modules
        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0045') # Multi-User Chat
        self.register_plugin('xep_0199') # XMPP Ping

        self.room = room
        self.nick = nick
        self.db_queue = db_queue
        self.to_links_queue = to_links_queue
        self.from_links_queue = from_links_queue

        self.add_event_handler("session_start", self.start)
        self.add_event_handler("groupchat_message", self.muc_message)
        self.add_event_handler("send_bot_message", self.send_bot_message)

    def start(self, event):
        self.get_roster()
        self.send_presence()
        self.plugin['xep_0045'].joinMUC(self.room,
                                        self.nick,
                                        wait=True)
        self.schedule('links_check', 1, self.check_links, repeat=True)

    def check_links(self):
        """Check if processed links queue isn't empty."""
        try:
            msg = self.from_links_queue.get_nowait()
            if msg:
                self.event("send_bot_message", {
                    'to': msg['to'],
                    'message': 'TITLE: {}'.format(msg['title'])
                })
        except queue.Empty:
            pass

    def send_bot_message(self, data):
        """Send message from bot."""
        self.send_message(mto=data['to'],
                          mbody=data['message'],
                          mtype='groupchat')

    def muc_message(self, msg):
        """Process message and do actions depending on its content."""
        nick = msg['mucnick']   # User nick sowed in chat room
        jid = str(msg['from'])  # ful JID Like user@jabb.en/UserName
        message = msg['body']   # Message body
        time_local = time.time()
        self.write_chat_log((time_local, jid, nick, message,))
        
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
               
                ### Ping command
            if command == 'ping':
                self.try_ping(msg['from'], msg['mucnick'])
       
            if command == 'version':
                self.send_message(mto=msg['from'].bare,
                                mbody="Bot version: %s." % BOT_VERSION,
                                mtype='groupchat')

    def try_ping(self, pingjid, nick):
        """Ping user."""
        logger.debug('Got ping from nick "%s" jid "%s"', nick, pingjid)
        try:
            rtt = self['xep_0199'].ping(pingjid,timeout=10)
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
