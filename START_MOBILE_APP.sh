#!/bin/bash
# Simple Mobile App Launcher - No Developer Setup Needed
# Just run this script and scan the QR code with Expo Go app on your iPhone

set -e

echo "📱 Starting Avira Mobile App..."
echo ""
echo "Prerequisites:"
echo "1. Install 'Expo Go' app from iPhone App Store"
echo "2. Make sure your iPhone and Mac are on the same WiFi network"
echo ""
echo "Starting in 3 seconds..."
sleep 3

cd /Users/harish/Documents/code/pla-avira/mobileapp

# Install expo if not already installed
if ! npm list expo > /dev/null 2>&1; then
    echo "Installing Expo..."
    npm install expo
fi

echo ""
echo "🚀 Starting Expo development server..."
echo ""
echo "📱 Open Expo Go app on your iPhone and scan the QR code below:"
echo ""

npx expo start --tunnel
