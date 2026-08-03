import pytest
from unittest.mock import AsyncMock
from backend.main import app
from backend.api.dependencies import get_chat_service
from fastapi.testclient import TestClient

@pytest.fixture
def mock_chat_service():
    mock = AsyncMock()
    mock.generate_answer.return_value = 'Mock LLM answer'
    mock.get_history.return_value = [
        {'user_id': 1, 'text_message': 'Hello', 'message_type': 0},
        {'user_id': 1, 'text_message': 'Hi', 'message_type': 1},
    ]
    return mock


@pytest.fixture
def client(mock_chat_service):
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    
    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides.clear()