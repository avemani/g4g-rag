from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    reranker_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
    litellm_url: str = Field(validation_alias='LITELLM_BASE_URL')
    litellm_api_key: str = Field(validation_alias='LITELLM_API_KEY')
    db_user: str = Field(validation_alias='WEBAPP_USER_DB')
    db_password: str = Field(validation_alias='WEBAPP_PASSWORD_DB')
    caching: bool = False
    tracking_uri: str = 'http://mlflow-server:5000'
    experiment_name: str = 'RAG_Hyperparameter_Tuning'

settings = Settings()