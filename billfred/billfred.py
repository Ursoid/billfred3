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

    def __init__(self, jid, password, rooms, rss, db_queue,
                 to_links_queue, to_rss_queue, msg_queue):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        # Load modules
        self.register_plugin('xep_0045') # Multi-User Chat
        self.register_plugin('xep_0199') # XMPP Ping

        self.rooms = rooms
        self.rss = rss
        self.db_queue = db_queue
        self.to_links_queue = to_links_queue
        self.to_rss = to_rss_queue
        self.msg_queue = msg_queue

        self.add_event_handler("session_start", self.start)
        self.add_event_handler("groupchat_message", self.muc_message)
        self.add_event_handler("send_bot_message", self.send_bot_message)

    def start(self, event):
        self.get_roster()
        self.send_presence()

        # Join all mucs
        for name, room in self.rooms.items():
            self.plugin['xep_0045'].joinMUC(room['room'],
                                            room['nick'],
                                            password=room['password'],
                                            wait=True)

        self.schedule('messages_check', 1, self.check_messages, repeat=True)

        # Add RSS checks to scheduler and do first check 
        i = 0
        for rss in self.rss:
            logger.info('Adding RSS task %s %s every %s seconds',
                        rss['prefix'], rss['url'], rss['time'])
            # First run to get initial articles, do it with interval
            self.schedule(
                'rss_check_{}'.format(rss['prefix']),
                i * 5,
                self.check_rss(rss['rooms'], rss['prefix'], rss['url']),
                repeat=False
            )
            i += 1
            # Now schedule periodic checks
            self.schedule(
                'rss_check_{}'.format(rss['prefix']),
                rss['time'],
                self.check_rss(rss['rooms'], rss['prefix'], rss['url']),
                repeat=True
            )

    def check_rss(self, rooms, prefix, url):
        """Return function that will put RSS check task."""
        def do_check():
            self.to_rss.put((rooms, prefix, url))
        return do_check

    def check_messages(self):
        """Check if new messages from threads are available."""
        try:
            msg = self.msg_queue.get_nowait()
            if msg:
                self.event("send_bot_message", {
                    'to': msg['to'],
                    'message': msg['message']
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
        room_jid = msg['from'].bare
        message = msg['body']   # Message body
        time_local = time.time()

        # Get room config for message
        current_room = None
        for name, room in self.rooms.items():
            if room['room'] == room_jid:
                current_room = room
                break
        if current_room is None:
            # What?
            self.logger.error('Message from unknown room: %s', msg)
            return
        
        self.write_chat_log((room['room'], time_local, jid, nick, message))
        
        # Disable self-interaction
        if msg['mucnick'] == room['nick']:
            return

        # Link title parser
        if 'http' in message:
            links = extract_links(message)
            self.to_links_queue.put([
                {'to': room_jid, 'link': l}
                for l in links[:self.links_limit]
            ])

        # Bot command parser
        if msg['body'].startswith(room['nick']):

            tokens = msg['body'].split()
            if len(tokens) > 1:
                command = tokens[1]
               
                ### Ping command
            if command == 'ping':
                self.try_ping(msg['from'], msg['mucnick'])
       
            if command == 'version':
                self.send_message(mto=room_jid,
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
