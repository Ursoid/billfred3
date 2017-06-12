import logging
import sqlite3

logger = logging.getLogger(__name__)


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
    
