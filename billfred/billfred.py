#!/usr/bin/env python
import sleekxmpp
import time
import logging

logger = logging.getLogger(__name__)

BOT_VERSION = 0.1


class Billfred(sleekxmpp.ClientXMPP):
    """Billfred chat bot."""

    def __init__(self, jid, password, room, nick, db_queue):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        # Load modules
        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0045') # Multi-User Chat
        self.register_plugin('xep_0199') # XMPP Ping

        self.room = room
        self.nick = nick
        self.db_queue = db_queue

        self.add_event_handler("session_start", self.start)
        self.add_event_handler("groupchat_message", self.muc_message)

    def start(self, event):
        self.get_roster()
        self.send_presence()
        self.plugin['xep_0045'].joinMUC(self.room,
                                        self.nick,
                                        wait=True)

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
