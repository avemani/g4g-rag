import asyncio
from os import getenv
from abc import ABC, abstractmethod
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING


MONGO_USER=getenv('MONGO_USER')
MONGO_PASS=getenv('MONGO_PASS')


class BaseMongoDBConnector(ABC):
    @abstractmethod
    async def import_data(self, data: list):
        raise NotImplementedError

    @abstractmethod
    async def extract_data(self, sources: list[str]) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def close_connection(self):
        raise NotImplementedError
    

class MongoDBConnector(BaseMongoDBConnector):
    def __init__(self, collection: str = 'math_data'):
        self.client = AsyncIOMotorClient(
            host='mongo',
            port=27017,
            username=MONGO_USER,
            password=MONGO_PASS,
            authSource='admin'
        )
        self.db=self.client['geekdb']
        self.collection=self.db[collection]


    async def import_data(self, data: list):
        if data:
            await self.collection.insert_many(data, ordered=False)


    async def extract_data(self, sources: list[str]) -> list[dict]:
        raw_data = self.collection.find({'source': {'$in': sources}}).sort('_id', ASCENDING)
        documents = await raw_data.to_list()

        return documents
    

    def close_connection(self):
        self.client.close()
