import asyncio
import asyncpg
from os import getenv
from abc import ABC, abstractmethod
from pgvector.asyncpg import register_vector
from pipeline.repository.geek_data import GeekData


POSTGRES_USER=getenv('POSTGRES_USER')
POSTGRES_PASSWORD=getenv('POSTGRES_PASSWORD')


class BasePostgresConnector(ABC):
    @abstractmethod
    async def init_connection(self):
        raise NotImplementedError
    
    @abstractmethod
    async def export_data(self, data: list[GeekData]):
        raise NotImplementedError

    @abstractmethod
    async def close_connection(self):
        raise NotImplementedError


class PostgresConnector(BasePostgresConnector):
    def __init__(self, schema_name: str = 'vectors', table_name: str = 'geek_rag_1024'):
        self.schema_name = schema_name
        self.table_name = table_name

    async def init_connection(self, host='postgres', port: int = 5432, database: str = 'geekdb'):
        self.conn = await asyncpg.connect(
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=database,
            port=port,
            host=host
        )

        await register_vector(self.conn)

    async def export_data(self, data: list[GeekData]):
        query = f"""
            INSERT INTO {self.schema_name}.{self.table_name}
            (url, title, subtitle, main_order, sub_order, text_data, embedding)
            values
            ($1, $2, $3, $4, $5, $6, $7)
        """

        turple_data = [(value.url, value.title, value.subtitle, value.main_order, value.sub_order, value.text_data, value.embedding) for value in data]

        await self.conn.executemany(query, turple_data)

    
    async def truncate_table(self):
        query = f'TRUNCATE TABLE {self.schema_name}.{self.table_name};'
        await self.conn.execute(query)


    async def close_connection(self):
        await self.conn.close()


