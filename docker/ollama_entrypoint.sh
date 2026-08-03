#!/bin/bash


/bin/ollama serve &
pid=$!

until ollama list >/dev/null 2>&1; do
  sleep 1
done

ollama pull llama3.1
ollama pull qwen2.5:3b
ollama pull qwen2.5:0.5b
ollama pull mxbai-embed-large

ollama run qwen2.5:3b "" > /dev/null 2>&1
ollama run qwen2.5:0.5b "" > /dev/null 2>&1

wait $pid