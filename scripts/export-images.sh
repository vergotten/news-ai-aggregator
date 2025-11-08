#!/bin/bash

# Создаём папку для кэша
mkdir -p docker_images_cache

echo "📦 Exporting Docker images to ./docker_images_cache/"
echo ""

# Список образов
IMAGES=(
    "postgres:15-alpine:postgres.tar"
    "qdrant/qdrant:latest:qdrant.tar"
    "ollama/ollama:latest:ollama.tar"
    "n8nio/n8n:latest:n8n.tar"
    "adminer:latest:adminer.tar"
    "ghcr.io/ai-dock/stable-diffusion-webui:v2-cuda-12.1.1-base-22.04-v2-v1.10.1:stable-diffusion.tar"
)

for entry in "${IMAGES[@]}"; do
    IFS=':' read -r image tag filename <<< "$entry"
    full_image="$image:$tag"
    filepath="docker_images_cache/$filename"

    if docker image inspect "$full_image" >/dev/null 2>&1; then
        echo "💾 Saving $full_image..."
        docker save -o "$filepath" "$full_image"
        size=$(du -h "$filepath" | cut -f1)
        echo "✅ Saved: $filename ($size)"
    else
        echo "⚠️  Not found: $full_image (skipping)"
    fi
    echo ""
done

echo "✅ Export complete!"
echo "📊 Cache size: $(du -sh docker_images_cache | cut -f1)"