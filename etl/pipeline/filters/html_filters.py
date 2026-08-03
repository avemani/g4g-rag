import re
from bs4 import BeautifulSoup
from abc import ABC, abstractmethod


class BaseHTMLFilter(ABC):
    @abstractmethod
    def include_class(self, soup: BeautifulSoup) -> BeautifulSoup:
        raise NotImplementedError

    @abstractmethod
    def exclude_classes(self, soup: BeautifulSoup):
        raise NotImplementedError

    @abstractmethod
    def exclude_types(self, soup: BeautifulSoup):
        raise NotImplementedError

    @abstractmethod
    def exclude_hidden_objects(self, soup: BeautifulSoup):
        raise NotImplementedError

    @abstractmethod
    def filter_url(self, href: str) -> bool:
        raise NotImplementedError



class HTMLFilter(BaseHTMLFilter):
    def __init__(self):
        self.class_to_include = r'^ArticlePagePostLayout.*'
        self.classes_to_exclude = (
            r'^ArticlePageBottomComponent.*', r'^ArticleQuiz.*',
            r'^ArticleHeader_last_updated.*'
        )
        self.types_to_exclude = (
            'script', 'style', 'header', 
            'footer', 'nav', 'aside', 'head'
        )
        self.base_url = 'https://www.geeksforgeeks.org/'
        self.forbidden_prefixes = (
            f'{self.base_url}page/',
            f'{self.base_url}search/',
            f'{self.base_url}work-experiences/',
            f'{self.base_url}category/',
            f'{self.base_url}dsa/',
            f'{self.base_url}tag/',
        )
        self.keywords = ('math', 'data', 'machine', 'learning')
        self.exclude_words = tuple(['/page/'])


    def include_class(self, soup: BeautifulSoup) -> BeautifulSoup:
        regex_pattern = re.compile(self.class_to_include)
        tag = soup.find(class_=regex_pattern)

        soup = BeautifulSoup(str(tag), 'lxml')
        return soup


    def exclude_classes(self, soup: BeautifulSoup):
        regex_patterns = [re.compile(pattern) for pattern in self.classes_to_exclude]
        for pattern in regex_patterns:
            for trash in soup.find_all(class_=pattern):
                trash.decompose()

    
    def exclude_types(self, soup: BeautifulSoup):
        for tags in soup(self.types_to_exclude):
            tags.decompose()


    def exclude_hidden_objects(self, soup: BeautifulSoup):
        for tags in soup(attrs={"hidden": True}):
            tags.decompose()


    def filter_url(self, href: str) -> bool:
        if (
            href.startswith(self.base_url) and
            not href.startswith(self.forbidden_prefixes) and 
            all(word not in href for word in self.exclude_words) and
            any(word in href for word in self.keywords) and
            href.count('/') > 3
        ):
            return True
        else:
            return False



