import asyncio
import sqlite3
import aiosqlite
from pathlib import Path
from abc import ABC, abstractmethod


class BaseSQLiteConversion(ABC):  
    @abstractmethod
    def init_sync_connection(self):
        raise NotImplementedError
    
    @abstractmethod
    async def init_async_connection(self):
        raise NotImplementedError
    
    @abstractmethod
    def create_table(self):
        raise NotImplementedError
    
    @abstractmethod
    def imoprt_data(self, href: str):
        raise NotImplementedError
    
    @abstractmethod
    def get_data(self, unparsed: bool = False) -> list[dict]:
        raise NotImplementedError
    
    @abstractmethod
    def close_sync_connection(self):
        raise NotImplementedError
    
    @abstractmethod
    async def close_async_connection(self):
        raise NotImplementedError
    
    @abstractmethod
    def refresh_data(self):
        raise NotImplementedError

    @abstractmethod
    async def set_parsed(self, id: int):
        raise NotImplementedError

    @abstractmethod
    async def set_skipped(self, id: int):
        raise NotImplementedError

    @abstractmethod
    async def set_unresolved(self, id: int, error: str):
        raise NotImplementedError



class SQLiteConversion(BaseSQLiteConversion):
    def __init__(self):
        self.db = Path('pipeline/data/href.db')
        self.table_name = 'urls_data'


    def init_sync_connection(self):
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        

    async def init_async_connection(self):
        self.conn = await aiosqlite.connect(self.db)
        await self.conn.execute('PRAGMA journal_mode=WAL;')
        await self.conn.execute('PRAGMA busy_timeout = 10000;')
        await self.conn.commit()


    def create_table(self):
        query = f'''
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL UNIQUE,
                is_parsed BOOL DEFAULT false NOT NULL,
                is_skipped BOOL DEFAULT false NOT NULL,
                unresolved_error BOOL DEFAULT false NOT NULL,
                error_data TEXT
            )
        '''
        self.cursor.execute(query)
        self.conn.commit()


    def imoprt_data(self, hrefs: list[tuple[str]]):
        query = f"INSERT INTO {self.table_name} (source) VALUES (?) ON CONFLICT DO NOTHING"
        self.cursor.executemany(query, hrefs)
        self.conn.commit()


    def get_data(self, unparsed: bool = False) -> list[dict]:
        data = []
        query = f'SELECT * FROM {self.table_name}'
        if unparsed:
            query += ' WHERE is_parsed = false'

        query += ' ORDER BY id'

        self.cursor.execute(query)

        columns = [column[0] for column in self.cursor.description]
        rows = self.cursor.fetchall()
        
        for row in rows:
            data.append(dict(zip(columns, row)))

        return data
    

    def refresh_data(self):
        query = f'''
            UPDATE {self.table_name}
            SET is_parsed = false,
                is_skipped = false,
                unresolved_error = false,
                error_data = NULL
        '''
        self.cursor.execute(query)
        self.conn.commit()
    

    def close_sync_connection(self):
        self.conn.close()


    async def close_async_connection(self):
        await self.conn.close()


    async def set_parsed(self, id: int):
        query = f'UPDATE {self.table_name} SET is_parsed = true WHERE id = {id}'
        async with self.conn.execute(query) as cursor:
            await self.conn.commit()


    async def set_skipped(self, id: int):
        query = f'UPDATE {self.table_name} SET is_skipped = true WHERE id = {id}'
        async with self.conn.execute(query) as cursor:
            await self.conn.commit()


    async def set_unresolved(self, id: int, error: str):
        query = f"UPDATE {self.table_name} SET unresolved_error = true, error_data = '{error}' WHERE id = {id}"
        async with self.conn.execute(query) as cursor:
            await self.conn.commit()