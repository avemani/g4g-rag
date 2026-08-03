#!/bin/bash


nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload > ./logs/uvicorn.log 2>&1 &
PYTHONPATH=. nohup streamlit run frontend/main.py > ./logs/streamlit.log 2>&1 &