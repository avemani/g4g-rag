from transformers import AutoTokenizer
from abc import ABC, abstractmethod
from os import path
import re


class BaseTokenTransformator(ABC):
    @abstractmethod
    def length_function(self) -> list[str]:
        raise NotImplementedError


class TokenTransformator(BaseTokenTransformator):
    def __init__(self, tokenizer_name: str):
        tokenizer_path = f'./tokenizer/{re.sub(r"[./:]", "_", tokenizer_name)}'

        if path.exists(tokenizer_path) and (
            path.exists(path.join(tokenizer_path, 'tokenizer.json')) or 
            path.exists(path.join(tokenizer_path, 'tokenizer_config.json'))
        ):
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
            self.tokenizer.save_pretrained(tokenizer_path)

    def length_function(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False, truncation=False, verbose=False))