from pydantic import BaseModel, Field


class HypotheticalMetadata(BaseModel):
    title: str = Field(description='Predicted title with SLM')
    subtitle: str = Field(description='Predicted subtitle with SLM')