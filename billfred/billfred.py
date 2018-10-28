#!/usr/bin/env python
import sleekxmpp
import time
import logging
import queue
from sleekxmpp.exceptions import IqError, IqTimeout

from billfred.links import extract_links

logger = logging.getLogger(__name__)

BOT_VERSION = 0.1


class Billfred(sleekxmpp.ClientXMPP):
    """Billfred chat bot."""
    # Amount of processed links in one message
    links_limit = 3

    def __init__(self, jid, password, room, nick, rss, db_queue,
                 to_links_queue, to_rss_queue, msg_queue):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        # Load modules
        self.register_plugin('xep_0045') # Multi-User Chat
        self.register_plugin('xep_0199') # XMPP Ping

        self.room = room
        self.nick = nick
        self.rss = rss
        self.db_queue = db_queue
        self.to_links_queue = to_links_queue
        self.to_rss = to_rss_queue
        self.msg_queue = msg_queue

        self.add_event_handler("session_start", self.start)
        self.add_event_handler("groupchat_message", self.muc_message)
        self.add_event_handler("send_bot_message", self.send_bot_message)

        self.schedule('messages_check', 1, self.check_messages, repeat=True)

        # Add RSS checks to scheduler and do first check 
        i = 1
        for prefix, url, time in self.rss:
            logger.info('Adding RSS task %s %s every %s seconds',
                        prefix, url, time)
            # First run to get initial articles, do it with interval
            self.schedule('rss_check_{}'.format(prefix), i * 5,
                          self.check_rss(prefix, url), repeat=False)
            i += 1
            # Now schedule periodic checks
            self.schedule('rss_check_{}'.format(prefix), time,
                          self.check_rss(prefix, url), repeat=True)

    def start(self, event):
        try:
            self.get_roster()
            self.send_presence()
            self.plugin['xep_0045'].joinMUC(self.room,
                                            self.nick,
                                            wait=True)
        except (IqError, IqTimeout) as e:
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
                self.send_bot_message({
                    'to': msg['from'].bare,
                    'message': "Bot version: {}".format(BOT_VERSION)
                })

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
