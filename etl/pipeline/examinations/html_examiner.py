from typing import Any
from bs4.element import Tag
from abc import ABC, abstractmethod


class BaseHTMLExaminer(ABC):
    @abstractmethod
    def line_examiner(self, obj: Tag, line_start: bool, line_end: bool) -> tuple[bool, bool]:
        raise NotImplementedError

    @abstractmethod
    def sign_examiner(self, obj: Tag, sign_start: str | bool, sign_end: str | bool) -> tuple[str | bool, str | bool]:
        raise NotImplementedError
    
    @abstractmethod
    def subtitle_examiner(self, obj: Tag, is_subtitle: bool) -> bool:
        raise NotImplementedError

    @abstractmethod
    def breaker_examiner(self, obj: Tag, br: bool) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def marker_examiner(self, obj: Tag, marker: bool) -> bool:
        raise NotImplementedError

    @abstractmethod
    def reset_flags(self, markers: dict) -> dict:
        raise NotImplementedError


class HTMLExaminer(BaseHTMLExaminer):
    def __init__(self, line_sings: tuple[str] = None, subtitle_signs: tuple[str] = None, script_signs: tuple[str] = None, marker: tuple[str] = None, breaker: tuple[str] = None):
        self.line_sings = line_sings or tuple(['p', 'blockquote', 'pre', 'h6', 'h5', 'h4', 'h3', 'h2', 'h1', 'ul', 'li'])
        self.subtitle_signs = subtitle_signs or tuple(['h1', 'h2'])
        self.script_signs = script_signs or tuple(['sub', 'sup'])
        self.breaker = breaker or tuple(['br'])
        self.marker = marker or tuple(['li'])


    def line_examiner(self, obj: Tag, line_start: bool, line_end: bool) -> tuple[bool, bool]:
        if obj.name in self.line_sings:
            line_start = True
            if not obj.find(True):
                line_end = True

        if obj.parent.name in self.line_sings and obj.find_next_sibling() is None:
            if not (obj.name == 'li' and obj.parent.name == 'ul') and not (obj.name in self.line_sings and obj.parent.name == 'blockquote'):
                line_end = True
            
        return line_start, line_end


    def sign_examiner(self, obj: Tag, sign_start: str | bool, sign_end: str | bool) -> tuple[str | bool, str | bool]:
        if obj.name in self.script_signs:
            sign_start = obj.name
            if not obj.find(True):
                sign_end = f'/{obj.name}'

        if obj.parent.name in self.script_signs and obj.find_next_sibling() is None:
            sign_end = f'/{obj.name}'

        return sign_start, sign_end
    

    def subtitle_examiner(self, obj: Tag, is_subtitle: bool) -> bool:
        if obj.name in self.subtitle_signs:
            is_subtitle = True

        return is_subtitle


    def breaker_examiner(self, obj: Tag, br: bool) -> bool:
        if obj.name in self.breaker:
            br = True

        return br

    
    def marker_examiner(self, obj: Tag, marker: bool) -> bool:
        if obj.name in self.marker:
            marker = True

        return marker
    

    def reset_flags(self, markers: dict) -> dict:
        for key in markers:
            markers[key] = False

        return markers