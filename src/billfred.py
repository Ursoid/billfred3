#!/usr/bin/env python

# SleekXMPP: The Sleek XMPP Library   Copyright (C) 2010  Nathanael C. Fritz
import sys
import os
import argparse

import logging
import logging.config

import sleekxmpp
import configparser

import sqlite3
import queue
import threading

import time

import feedparser

# Get billfred logger
logger = logging.getLogger('billfred')

BOT_VERSION = 0.1
rss_feeds = []

def db_thread(path, queue):
    """Thread function that writes log to sqlite db."""
    logger.info('Opening database %s', path)
    db = sqlite3.connect(path)

    # Create table if we have a new database
    cursor = db.cursor()
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS chat_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time  INTEGER NOT NULL,
        jit TEXT NOT NULL,
        name TEXT NOT NULL,
        message TEXT
        )'''
    )
    cursor.close()

    # Main listening loop
    while True:
        query = queue.get()
        # Stop thread when 'stop' received
        if query == 'stop':
            break
        cursor = db.cursor()
        logger.debug('Writing %s to database', query)
        cursor.execute(
            'INSERT INTO chat_log (time, jit, name, message) VALUES (?,?,?,?)',
            query
        )
        cursor.close()
        db.commit()
    logger.info('Closing database %s', path)
    db.close()


class BBot(sleekxmpp.ClientXMPP):
    """Billfred chat bot."""
    def __init__(self, jid, password, room, nick, queue):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        self.room = room
        self.nick = nick
        self.queue = queue

        self.add_event_handler("session_start", self.start)
        self.add_event_handler("groupchat_message", self.muc_message)
        self.add_event_handler("muc::%s::got_online" % self.room,
                               self.muc_online)

    def start(self, event):
        self.get_roster()
        self.send_presence()
        self.plugin['xep_0045'].joinMUC(self.room,
                                        self.nick,
                                        wait=True)

    def muc_message(self, msg):
        # Cmopose data and write message to  chat log
        nick = msg['mucnick'] # User nick sowed in chat room
        jid = str(msg['from'])     # ful JID Like user@jabb.en/UserName
        message = msg['body'] # Message body
        time_local = time.time()
        self.write_chat_log((time_local, jid, nick, message,))

        
        #if msg['mucnick'] != self.nick and self.nick in msg['body']:
        #    self.send_message(mto=msg['from'].bare,
        #                      mbody="I heard that, %s." % msg['mucnick'],
        #                      mtype='groupchat')
        
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
            if command == 'feeds':
                for feed in rss_feeds:
                    self.send_message(mto=msg['from'].bare,
                                mbody="monitoring:  %s  in %s seconds period." % (feed[0], feed[1]),
                                mtype='groupchat')


        elif "http" in msg['body']:
            return
            #self.try_say_url_info(msg['body'], msg['from'])

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


    def muc_online(self, presence):
        #if presence['muc']['nick'] != self.nick:
        #    self.send_message(mto=presence['from'].bare,
        #                      mbody="Hello, %s %s" % (presence['muc']['role'],
        #                                              presence['muc']['nick']),
        #                      mtype='groupchat')
        return

    def write_chat_log(self, query):
        self.queue.put(query)

#   def rss_update(self):
#       url_rss = 'http://rulinux.net/rss'
#       rss_depth_time = 600
#       current_time = datetime.datetime.utcnow()
#
#       try:
#           rss = feedparser.parse(url_rss)
#           for r in rss.entries:
#               time_rss = datetime.datetime.fromtimestamp(time.mktime(r.published_parsed))
#               #print current_time
#               t = current_time - time_rss
#               #TODO: normal time pars not like {-(3600*3)} for remove 3 hour
#               time_delta = t.total_seconds()-(3600*3)
#               if (0 < time_delta)  and (time_delta < rss_depth_time):
#                   news_title = unicode(r.title)
#                   news_link  = unicode(r.link)
#                   self.send_message(mto="rulinux@conference.jabber.ru",
#                           mbody="RULIN: %s %s" % (news_title, news_link),
#                           mtype='groupchat')
#               else:
#                   break
#       except:
#           logging.info("DEBUG: RSS Feed problem, %s" , sys.exc_info()[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A jabber bot.')
    parser.add_argument(
        '--config',
        default=os.path.join(os.path.dirname(__file__), 'billfred.cfg'),
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
        db_path = os.path.join(os.path.dirname(__file__),
                               '{}_chatlog.db'.format(room))

    db_queue = queue.Queue()
    xmpp = BBot(jid, password, room, nick, db_queue)

    # Load RSS feeds
    for param in config['rss'].values():
        rss_feeds.append(param.split(" "))
   
    # Load modules
    xmpp.register_plugin('xep_0030') # Service Discovery
    xmpp.register_plugin('xep_0045') # Multi-User Chat
    xmpp.register_plugin('xep_0199') # XMPP Ping

    # Start thread for logging
    db_thread = threading.Thread(target=db_thread, args=(db_path, db_queue))
    db_thread.start()

    # Connect to the XMPP server and start processing XMPP stanzas.
    try:
        if xmpp.connect():
            xmpp.process(block=True)
        else:
            logger.error('Unable to connect')
    finally:
        # Always close db thread
        db_queue.put('stop')
        db_thread.join()
    logger.info('Done')
