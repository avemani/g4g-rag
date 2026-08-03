import random
import asyncio
from datetime import datetime
from abc import ABC, abstractmethod
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
from playwright.async_api._generated import Page, Browser, BrowserContext
from pipeline.connections.parser_api import ParserAPI
from pipeline.connections.mongodb_connection import MongoDBConnector
from pipeline.connections.sqlite_connector import SQLiteConversion


class BaseDataCollector(ABC):
    @abstractmethod
    def get_hrefs(self, unparsed: bool = True) -> list[dict]:
        raise NotImplementedError
    
    @abstractmethod
    def collect_hrefs(self):
        raise NotImplementedError
    
    @abstractmethod
    async def collect_one(self, page: Page, sql_conversion: SQLiteConversion, mongo_importer: MongoDBConnector, source: dict):
        raise NotImplementedError
    
    @abstractmethod
    async def create_pages(self, browser: Browser, n_threads: int) -> tuple[BrowserContext, list[Page]]:
        raise NotImplementedError
    
    @abstractmethod
    async def collect_data(self):
        raise NotImplementedError
    

class DataCollector(BaseDataCollector):
    def __init__(self, url: str = 'https://www.geeksforgeeks.org/machine-learning/ai-ml-and-data-science-tutorial-learn-ai-ml-and-data-science/'):
        self.url: str = url


    def get_hrefs(self, unparsed: bool = True) -> list[dict]:
        sql = SQLiteConversion()
        sql.init_sync_connection()

        try:
            data = sql.get_data(unparsed=unparsed)
        finally:
            sql.close_sync_connection()

        return data


    def collect_hrefs(self):
        sql_conversion = SQLiteConversion()
        sql_conversion.init_sync_connection()
        api = ParserAPI(self.url)

        try:
            sql_conversion.create_table()
            sql_conversion.refresh_data()

            while api.hrefs:
                api.get_href()
            
            api.collected_hrefs = set([tuple([href]) for href in api.collected_hrefs])
            sql_conversion.imoprt_data(api.collected_hrefs)
        finally:
            sql_conversion.close_sync_connection()

    
    async def collect_one(self, page: Page, sql_conversion: SQLiteConversion, mongo_importer: MongoDBConnector, source: dict):
        api = ParserAPI(source['source'], source['id'])
        data = await api.download_data(page, sql_conversion)

        await mongo_importer.import_data(data)
        await sql_conversion.set_parsed(source['id'])

    
    async def create_pages(self, browser: Browser, n_threads: int) -> tuple[BrowserContext, list[Page]]:
        context = await browser.new_context()

        pages = []
        for _ in range(n_threads):
            page = await context.new_page()
            pages.append(page)

        return context, pages


    async def close_pages(self, context: BrowserContext, pages: list[Page]):
        for page in pages:
            await page.close()

        await context.close()


    async def collect_data(self, n_threads: int = 1):
        mongo_importer = MongoDBConnector()
        sql_conversion = SQLiteConversion()

        sources = await asyncio.to_thread(self.get_hrefs)

        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch(headless=True, args=[
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ])

                context, pages = await self.create_pages(browser, n_threads)
                await sql_conversion.init_async_connection()

                for i in range(0, len(sources), n_threads):
                    
                    if i % 100 < n_threads:
                        print(f'Cool down ({i} page): {datetime.now()}')
                        await self.close_pages(context, pages)
                        context, pages = await self.create_pages(browser, n_threads)
                        await asyncio.sleep(random.uniform(60, 90))
                        
                    chunk = sources[i: i + n_threads]
                    tasks = []

                    for j, source in enumerate(chunk):
                        tasks.append(self.collect_one(pages[j], sql_conversion, mongo_importer, source))

                    await asyncio.gather(*tasks)
            finally:
                mongo_importer.close_connection()
                await sql_conversion.close_async_connection()
                await self.close_pages(context, pages)
                await browser.close()