#!/bin/bash
SERVICE=${1:-app}
echo "📊 Логи: $SERVICE"
docker-compose logs -f $SERVICE
