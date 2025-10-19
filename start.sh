#!/bin/bash
echo "🚀 Запуск News Aggregator..."
docker-compose up -d
echo ""
echo "✅ Сервисы запущены!"
echo ""
echo "Streamlit:  http://localhost:8501"
echo "N8N:        http://localhost:5678"
echo "Adminer:    http://localhost:8080"
echo "Ollama:     http://localhost:11434"
