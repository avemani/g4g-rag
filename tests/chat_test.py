def test_chat_api_success(client, mock_chat_service):
    request_payload = {
        'user_id': 1, 
        'message': 'My mock question here'
    }

    response = client.post('api/v1/chat/', json=request_payload)
    
    assert response.status_code == 200, f'API POST Error: {response.text}'
    
    data = response.json()
    
    assert 'reply' in data
    assert data['reply'] == 'Mock LLM answer'
    
    mock_chat_service.save_history.assert_any_call(user_id=1, text='My mock question here', message_type=0)
    mock_chat_service.generate_answer.assert_called_once_with(
        query='My mock question here', 
        use_kword=False, 
        use_meta=True, 
        use_rerank=True, 
        k=50, 
        limit=30, 
        t=3
    )


def test_chat_history_success(client, mock_chat_service):
    response = client.get('api/v1/chat/history?user_id=1')
    
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 2
    assert data[0]['text_message'] == 'Hello'