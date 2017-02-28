#!/usr/bin/env python
# -*- coding: utf-8 -*-

# SleekXMPP: The Sleek XMPP Library   Copyright (C) 2010  Nathanael C. Fritz


import sys
import os

import logging

import sleekxmpp
import configparser

import sqlite3
import queue
import threading

import time



# use UTF-8 encoding
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')
else:
    raw_input = input

#path + name
db_full_path=""
#Queue for messages  to write
queue = queue.Queue()


#Open sqlite thread  and write log  from queue
def db_thread(queue):
    connect_db = sqlite3.connect(db_full_path)
    while True:
        query = queue.get()
        cursor_db = connect_db.cursor()
        #logging.info("DEBUG: Query writing to file")
        cursor_db.execute("""INSERT INTO chat_log (id, time, jit, name, message)
                            VALUES (NULL,?,?,?,?)""", query)
        connect_db.commit()
        #TODO:  add  EOF command  to queue  for normal  close DB connection
    connect_db.close()


class BBot(sleekxmpp.ClientXMPP):

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

        
        if msg['mucnick'] != self.nick and self.nick in msg['body']:
            self.send_message(mto=msg['from'].bare,
                              mbody="I heard that, %s." % msg['mucnick'],
                              mtype='groupchat')
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
               
        elif "http" in msg['body']:
            return
            #self.try_say_url_info(msg['body'], msg['from'])

    def try_ping(self, pingjid, nick):
        try:
            rtt = self['xep_0199'].ping(pingjid,timeout=10)
            self.send_message(mto=pingjid.bare,
                                mbody="%s, pong is: %s" % (nick, rtt),
                                mtype='groupchat')
                #logging.info("Success! RTT: %s", rtt)
        except IqError as e:
            logging.info("Error pinging %s: %s",
                    pingjid,
                    e.iq['error']['condition'])
        except IqTimeout:
            logging.info("No response from %s", pingjid)


    def muc_online(self, presence):
        if presence['muc']['nick'] != self.nick:
            self.send_message(mto=presence['from'].bare,
                              mbody="Hello, %s %s" % (presence['muc']['role'],
                                                      presence['muc']['nick']),
                              mtype='groupchat')

    def write_chat_log(self, query):
        self.queue.put(query)
     
  

            
if __name__ == '__main__':
    #load config file 
    config = configparser.ConfigParser()
    config.read('billfred.cfg')

    #Setup logging.
    loglevel = config['log']['loglevel']
    logging.basicConfig(level=loglevel,
                        format='%(levelname)-8s %(message)s')
    
    #Database
    dbname = config['database']['database_name'] 
    if not dbname:
        dbname = config['account']['room'] + "_chatlog.db"
    dbpath = config['database']['database_path']
    if not dbpath:
        dbpath = os.path.dirname(__file__)
    db_full_path =  os.path.join(dbpath, dbname)
     
    if not os.path.isfile(db_full_path):    
        connect_db = sqlite3.connect(db_full_path)
        cursor_db = connect_db.cursor()
        
        cursor_db.execute("""CREATE TABLE chat_log(id INTEGER PRIMARY KEY AUTOINCREMENT,
                            time  INTEGER NOT NULL,
                            jit TEXT NOT NULL,
                            name TEXT NOT NULL,
                            message TEXT)""")
        connect_db.close()
        print("warning: New chat log database was created")

    #Start writing queue for loging chat
    threading.Thread(target=db_thread, args=(queue,)).start()

    #Connect to account
    jid = config['account']['jid'] 
    password = config['account']['password']
    room = config['account']['room']
    nick = config['account']['nick']
    if (not jid) or (not password) or (not room):
        #debug print('{:<5}| jid'.format(jid))
        print("wrong account parametrs.  exit...")
        sys.exit(78);        
    xmpp = BBot(jid, password, room, nick, queue)

    #Load modules
    xmpp.register_plugin('xep_0030') # Service Discovery
    xmpp.register_plugin('xep_0045') # Multi-User Chat
    xmpp.register_plugin('xep_0199') # XMPP Ping

    # Connect to the XMPP server and start processing XMPP stanzas.
    if xmpp.connect():
        xmpp.process(block=True)
        print("Done")
    else:
        print("Unable to connect.")
