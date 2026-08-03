import random
import asyncio
import requests
from time import sleep
from datetime import datetime
from abc import ABC, abstractmethod
from requests.sessions import Session
from bs4 import BeautifulSoup, NavigableString
from playwright.sync_api._generated import Page
from playwright.sync_api import TimeoutError, Error
from pipeline.filters.html_filters import HTMLFilter
from pipeline.examinations.html_examiner import HTMLExaminer
from pipeline.connections.sqlite_connector import SQLiteConversion


class BaseParserAPI(ABC):
    @abstractmethod
    def save_skipped(self):
        raise NotImplementedError

    @abstractmethod
    def get_href(self):
        raise NotImplementedError

    @abstractmethod
    def connect_to_url(self, page: Page) -> bool:
        raise NotImplementedError

    @abstractmethod
    def deep_scan(self, soup: BeautifulSoup, data: list[dict], order: int, markers: dict) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def download_data(self, url: str) -> dict:
        raise NotImplementedError
    


class ParserAPI(BaseParserAPI):
    def __init__(self, url: str, id: int | None = None):
        self.url: str = url
        self.id: int | None = id
        self.hrefs: list[str] = [url]
        self.collected_hrefs: set[tuple[str]] | set[str] = set()
        self.last_href: str | None = None
        self.fltr = HTMLFilter()
        self.order = 1
        self.markers = {
            'line_start': False,
            'line_end': False,
            'is_subtitle': False,
            'sign_start': False,
            'sign_end': False,
            'marker': False,
            'br': False,
        }        


    def save_skipped(self):
        with open('pipeline/metadata/skipped.txt', 'a') as file:
            file.write(f'{self.url}\n')


    def get_href(self):
        headers = {"User-Agent": "Mozilla/5.0"}
        current_url = self.hrefs.pop(0)

        if current_url not in self.collected_hrefs:
            for _ in range(3):
                try:
                    response = requests.get(current_url, timeout=30, headers=headers)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'lxml')

                    soup = self.fltr.include_class(soup)
                    self.fltr.exclude_types(soup)
                    self.fltr.exclude_hidden_objects(soup)
                    self.fltr.exclude_classes(soup)
                
                    for obj in soup.find_all(href=True):
                        href = obj.get('href')
                        if self.fltr.filter_url(href):
                            if href not in self.collected_hrefs:
                                self.hrefs.append(href)

                    self.collected_hrefs.add(current_url)
                    break
                except requests.exceptions.HTTPError:
                    print(f'Paused: {datetime.now()}')
                    sleep(300)
                except requests.exceptions.TooManyRedirects:
                    print(f'Too many redirects: {current_url}')
                    break


    async def connect_to_url(self, page: Page, sql_conversion: SQLiteConversion) -> bool:
        await asyncio.sleep(random.uniform(3, 5))
        error_message = 'Timeout Error. Exceed number of tries'
        
        for i in range(3):
            try:
                response = await page.goto(self.url, timeout=180000, wait_until='domcontentloaded')

                if response is not None:
                    if response.status >= 400:
                        if response.status == 404:
                            print(f'Server responded with status {response.status}')
                            break
                        else:
                            raise TimeoutError(f'Server responded with status {response.status}')
                    
                else:
                    if page.url == 'about:blank':
                        error_message = f'Navigation failed completely. No content to read.\nTarget url: {self.url}'
                        print(error_message)
                        await sql_conversion.set_skipped(self.id)
                        await sql_conversion.set_unresolved(self.id, error_message)
                        
                        return False
                    else:
                        content = await page.content()

                        if 'html' not in content:
                            error_message = f'No response from the server.\nTarget url: {self.url}\nNavigated url: {page.url}'
                            raise TimeoutError(error_message)
                        else:
                            return True
                        
                return True
            except TimeoutError as error:
                if i < 2:
                    print(f'Timeout Error: {error}')
                    print(f'Paused: {datetime.now()}')
                    await asyncio.sleep(180)
            except Error as error:
                if i < 2:
                    print(f'Unresolved Error. Paused: {datetime.now()}')
                    await asyncio.sleep(180)
                else:
                    print(f'Unresolved error: {error}')
                    await sql_conversion.set_skipped(self.id)
                    await sql_conversion.set_unresolved(self.id, error)
                    return False
        
        print('Exceed number of tries.')
        print(self.url)
        await sql_conversion.set_skipped(self.id)
        await sql_conversion.set_unresolved(self.id, error_message)
        return False
            

    async def deep_scan(self, soup: BeautifulSoup, data: list[dict]) -> list[dict]:
        examiner = HTMLExaminer()

        for child in soup.children:
            if not isinstance(child, NavigableString):
                text = child.get_text(strip=False)
                href = child.get('href')

                if href:
                    self.last_href = href

                if href and self.fltr.filter_url(href):
                    self.hrefs.append(href)

                self.markers['line_start'], self.markers['line_end'] = examiner.line_examiner(child, self.markers['line_start'], self.markers['line_end'])
                self.markers['sign_start'], self.markers['sign_end'] = examiner.sign_examiner(child, self.markers['sign_start'], self.markers['sign_end'])

                self.markers['is_subtitle'] = examiner.subtitle_examiner(child, self.markers['is_subtitle'])
                self.markers['marker'] = examiner.marker_examiner(child, self.markers['marker'])
                self.markers['br'] = examiner.breaker_examiner(child, self.markers['br'])

                if not child.find(True):
                    if text or self.markers['br']:
                        if text and self.last_href:
                            if text.strip(' :.') == 'click here':
                                text = self.last_href
                        attrs = {
                            'source': self.url,
                            'order': self.order,
                            'type': child.name,
                            'name': child.get('name'),
                            'class': child.get('class', []),
                            'line_start': self.markers['line_start'],
                            'line_end': self.markers['line_end'],
                            'sign_start': self.markers['sign_start'],
                            'sign_end': self.markers['sign_end'],
                            'is_subtitle': self.markers['is_subtitle'],
                            'marker': self.markers['marker'],
                            'breaker': self.markers['br'],
                            'text': text,
                        }

                        item = {key: value for key, value in attrs.items() if value}
                        self.markers = examiner.reset_flags(self.markers)

                        data.append(item)
                        self.order += 1
                else:
                    await self.deep_scan(child, data)
            else:
                if child.parent.name == 'pre':
                    text = child.get_text(strip=False)
                else:
                    text = child.get_text(strip=False).strip('\n')
                if text:
                    if text == 'click here':
                        text = href
                    attrs = {
                        'source': self.url,
                        'order': self.order,
                        'type': 'raw',
                        'line_start': self.markers['line_start'],
                        'line_end': self.markers['line_end'],
                        'text': text,
                    }

                    self.markers['line_start'], self.markers['line_end'] = examiner.line_examiner(child, self.markers['line_start'], self.markers['line_end'])
                    self.markers['sign_start'], self.markers['sign_end'] = examiner.sign_examiner(child, self.markers['sign_start'], self.markers['sign_end'])
                    self.markers = examiner.reset_flags(self.markers)

                    item = {key: value for key, value in attrs.items() if value}

                    data.append(item)
                    self.order += 1

        return data

    
    async def download_data(self, page: Page, sql_conversion: SQLiteConversion) -> list[dict]:
        data = []

        connected = await self.connect_to_url(page, sql_conversion)

        if not connected:
            return

        content = await page.content()
        soup = BeautifulSoup(content, 'lxml')

        soup = self.fltr.include_class(soup)
        self.fltr.exclude_types(soup)
        self.fltr.exclude_hidden_objects(soup)
        self.fltr.exclude_classes(soup)

        data = await self.deep_scan(soup, data)

        return data