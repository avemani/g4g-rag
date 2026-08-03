import asyncio
from pipeline.core.data_collection import DataCollector


if __name__ == '__main__':
    collector = DataCollector()
    asyncio.run(collector.collect_data(n_threads=8))