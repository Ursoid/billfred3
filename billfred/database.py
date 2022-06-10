import time
import logging
import aiosqlite

logger = logging.getLogger(__name__)


class Database:
    """Async database wrapper."""
    VERSION = '0.2'

    def __init__(self, path):
        self.path = path
        self.db = None

    async def init(self):
        """Create db connection and initialize db structure."""
        logger.info('Connecting to db %s', self.path)
        self.db = await aiosqlite.connect(self.path)
        await self.create_db()
        await self.migrate_db()

    async def create_db(self):
        """Create database if not exists."""
        logger.info('Creating missing tables')
        await self.db.execute(r'''
        CREATE TABLE IF NOT EXISTS chat_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          time INTEGER NOT NULL,
          jid TEXT NOT NULL,
          nick TEXT NOT NULL,
          message TEXT
        )''')
        await self.db.execute(r'''
        CREATE TABLE IF NOT EXISTS version (
          id INTEGER PRIMARY KEY,
          time INTEGER NOT NULL,
          version TEXT NOT NULL
        )''')
        await self.db.commit()

    async def migrate_db(self):
        """Migrate database from old structure to new one if required.."""
        async with self.db.execute(
                r'SELECT version FROM version ORDER BY time DESC LIMIT 1'
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0] == self.VERSION:
                # Already migrated
                logger.info('Database is up to date')
                return

        # Only pre-0.2 supported now
        logger.info('Migrating database to %s', self.VERSION)
        await self.db.execute(
            r'ALTER TABLE chat_log RENAME COLUMN jit TO jid'
        )
        await self.db.execute(
            r'ALTER TABLE chat_log RENAME COLUMN name TO nick'
        )

        # Migrated successfully
        await self.db.execute(
            r'INSERT INTO version (id, time, version) VALUES (?, ?, ?)',
            (1, time.time(), self.VERSION)
        )
        await self.db.commit()
        logger.info('Updated to version %s', self.VERSION)

    async def write(self, message):
        """Write message to database."""
        try:
            args = (time.time(), str(message.get('from')),
                    message.get('mucnick'), message.get('body'))
            logger.debug('Writing message %s', args)
            await self.db.execute(
                (r'INSERT INTO chat_log (time, jid, nick, message) '
                 'VALUES (?, ?, ?, ?)'), args
            )
            await self.db.commit()
        except Exception:
            logger.exception('Can not write message to database')

    async def close(self):
        """Destroy db connection."""
        if self.db:
            logger.info('Closing db')
            await self.db.close()
