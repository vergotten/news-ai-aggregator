#!/bin/bash
echo "⚠️  ВНИМАНИЕ: Это удалит все данные!"
read -p "Продолжить? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Удаление volumes и контейнеров..."
    docker-compose down -v
    rm -rf data/* logs/* sessions/*
    echo "✅ Очистка завершена"
else
    echo "❌ Отменено"
fi
