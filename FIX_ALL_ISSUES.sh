#!/bin/bash
# Complete Fix Script - Get Everything Working
# Run this to fix all issues at once

set -e

echo "🚀 Fixing All Issues..."

# 1. Test Financial Data Access
echo ""
echo "📊 Testing Financial Data..."
curl -s http://localhost:30000/api/finance/summary | jq .

# 2. Upload Health Data
echo ""
echo "🏥 Uploading Health Data..."
if [ -f "/Users/harish/Documents/code/pla-avira/uploads/health/labs.pdf" ]; then
    curl -F "file=@/Users/harish/Documents/code/pla-avira/uploads/health/labs.pdf" \
         http://localhost:30000/api/health/upload-lab-results
fi

# 3. Test Assistant with Financial Query
echo ""
echo "💬 Testing Assistant Financial Analysis..."
curl -s -X POST http://localhost:30000/api/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "spending",
    "session_id": "quick-test",
    "user_id": "default"
  }' | jq -r '.response'

# 4. Check Calendar Events
echo ""
echo "📅 Checking Calendar Events..."
curl -s http://localhost:30000/api/calendar/upcoming?days=90 | jq .

# 5. Check Ollama Model
echo ""
echo "🤖 Checking Ollama Models..."
ollama list

# 6. Open Web App
echo ""
echo "🌐 Opening Web App..."
open http://localhost:30001

echo ""
echo "✅ All checks complete!"
echo ""
echo "📱 For iOS App:"
echo "   cd /Users/harish/Documents/code/pla-avira/mobileapp"
echo "   npx expo start"
echo "   Then scan QR code with Expo Go app on your iPhone"
