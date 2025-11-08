#!/bin/bash

if [ ! -d "docker_images_cache" ]; then
    echo "❌ Cache folder not found"
    exit 1
fi

echo "📦 Importing Docker images from ./docker_images_cache/"
echo ""

cd docker_images_cache

for tarfile in *.tar; do
    if [ -f "$tarfile" ]; then
        echo "⬆️  Loading $tarfile..."
        if docker load -i "$tarfile"; then
            echo "✅ Loaded successfully"
        else
            echo "❌ Failed to load $tarfile"
        fi
        echo ""
    fi
done

echo "✅ Import complete!"
docker images