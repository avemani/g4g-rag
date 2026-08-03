from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeekData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[int] = Field(alias='id', default=None, description='PostgreSQL BIGSERIAL')
    url: str = Field(alias='source')
    title: str = Field(alias='title')
    subtitle: str = Field(alias='subtitle')
    main_order: int = Field(alias='main_order')
    sub_order: int = Field(alias='order')
    text_data: str = Field(alias='chunks')
    embedding: List = Field(alias='embedding')

    @field_validator('embedding', mode='before')
    @classmethod
    def check_rag(cls, obj):
        if len(obj) == 1024:
            return obj

        print(f'Embdding has an unsupported type or shape:\n\t {type(obj)}: {len(obj)}')
        raise ValueError