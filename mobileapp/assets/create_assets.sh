#!/bin/bash
# Create simple placeholder assets using base64 encoded 1x1 PNG
echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" | base64 -d > icon.png
cp icon.png splash.png
cp icon.png adaptive-icon.png
cp icon.png favicon.png
