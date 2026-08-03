import pynvml
import asyncio
from os import getenv
from tqdm import tqdm
from datetime import datetime
from abc import ABC, abstractmethod
from pipeline.connections.postgres_connector import PostgresConnector
from pipeline.connections.sqlite_connector import SQLiteConversion
from pipeline.connections.mongodb_connection import MongoDBConnector
from pipeline.transformers.geek_data_transformer import GeekTransformer


BATCH_SIZE = int(getenv('BATCH_SIZE') or 512)
LLM_MODEL = getenv('LLM_MODEL') or 'qwen2.5:3b'
TOKENIZER = getenv('TOKENIZER') or 'mixedbread-ai/mxbai-embed-large-v1'
EMBEDDING_MODEL = getenv('EMBEDDING_MODEL') or 'mxbai-embed-large'
CHUNK_SIZE = int(getenv('CHUNK_SIZE') or 400)
CHUNK_OVERLAP = int(getenv('CHUNK_OVERLAP') or CHUNK_SIZE * 0.1)

class BaseDataMigrator(ABC):
    @abstractmethod
    def migrate_data(self):
        raise NotImplementedError
        

class DataMigrator(BaseDataMigrator):
    async def migrate_data(self, truncate: bool = False):
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        try:
            sqlite_conversion = SQLiteConversion()
            mongodb_connector = MongoDBConnector()
            postgres_connector = PostgresConnector()
            transformer = GeekTransformer(
                tokenizer=TOKENIZER,
                batch_size=BATCH_SIZE,
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                embedding_model=EMBEDDING_MODEL
            )

            sqlite_conversion.init_sync_connection()
            hrefs = sqlite_conversion.get_data()
            sqlite_conversion.close_sync_connection()

            await postgres_connector.init_connection()

            if truncate:
                await postgres_connector.truncate_table()

            for i in tqdm(range(0, len(hrefs), BATCH_SIZE), desc='Embedding Progress'):
                batch = hrefs[i: i + BATCH_SIZE]
                href_batch = [item['source'] for item in batch]
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000 
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                print(f'Temp: {temp}°C | Power: {power:.1f}W | GPU Util: {util.gpu}% | VRAM Util: {util.memory}% ({datetime.now()})')

                if temp > 85:
                    print(f'Temperature is to high. Cool down for 5 min ({datetime.now()})')
                    await asyncio.sleep(300)

                documents = await mongodb_connector.extract_data(href_batch)
                data = transformer.transoform(documents)

                await postgres_connector.export_data(data)

            mongodb_connector.close_connection()
            await postgres_connector.close_connection()
        finally:
            pynvml.nvmlShutdown()



