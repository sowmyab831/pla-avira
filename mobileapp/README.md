# Avira Mobile App

Cross-platform React Native mobile app for iOS and Android that connects to your self-hosted Avira backend.

## Features

- 🤖 **AI Assistant** - Shopping, travel, health & finance queries
- 🛒 **Shopping** - Product search and price comparison
- ✈️ **Travel** - Flight search with comfort scoring
- 💰 **Finance** - Budget tracking and spending analysis
- ❤️ **Health** - Lab results and health alerts
- 📅 **Calendar** - Events and appointments
- 🔒 **Privacy** - Automatic PII/PCI masking

## Prerequisites

- Node.js 18+
- React Native CLI
- Xcode (for iOS)
- Android Studio (for Android)
- CocoaPods (for iOS)

## Setup

### 1. Install Dependencies

```bash
cd mobileapp
npm install

# iOS only
cd ios && pod install && cd ..
```

### 2. Configure API Endpoint

The app connects to your DuckDNS endpoint by default:
- **Production**: `http://aviraa.duckdns.org:30000`
- **Local**: `http://localhost:30000`

To change, edit `src/services/api.ts`:

```typescript
const CONFIG = {
  PRODUCTION_API: 'http://aviraa.duckdns.org:30000',
  LOCAL_API: 'http://localhost:30000',
  DIRECT_IP_API: 'http://65.188.101.168:30000',
};
```

### 3. DuckDNS Setup

1. Go to https://www.duckdns.org
2. Login with Google/GitHub
3. Create domain: `aviraa`
4. Note your token
5. Run setup script:

```bash
# Edit the token first
nano ../scripts/setup-duckdns.sh

# Run setup
chmod +x ../scripts/setup-duckdns.sh
../scripts/setup-duckdns.sh
```

### 4. Port Forwarding

Configure your router to forward:
- Port 30000 → Your server's local IP:30000 (API)
- Port 30080 → Your server's local IP:30080 (Web)

## Running the App

### iOS

```bash
# Start Metro bundler
npm start

# In another terminal
npm run ios

# Or open in Xcode
open ios/AviraApp.xcworkspace
```

### Android

```bash
# Start Metro bundler
npm start

# In another terminal
npm run android

# Or open in Android Studio
# File → Open → mobileapp/android
```

## Building for Release

### iOS (App Store)

```bash
# In Xcode:
# 1. Select "Any iOS Device" as target
# 2. Product → Archive
# 3. Distribute App → App Store Connect
```

### Android (Play Store)

```bash
cd android
./gradlew bundleRelease

# APK will be at:
# android/app/build/outputs/bundle/release/app-release.aab
```

## Project Structure

```
mobileapp/
├── App.tsx                 # Main entry point
├── index.js                # React Native entry
├── app.json                # App configuration
├── package.json            # Dependencies
├── src/
│   ├── screens/
│   │   ├── HomeScreen.tsx      # Dashboard
│   │   └── AssistantScreen.tsx # AI Chat
│   ├── services/
│   │   └── api.ts              # API client
│   ├── components/             # Reusable components
│   └── hooks/                  # Custom hooks
├── android/                # Android native code
├── ios/                    # iOS native code
└── assets/                 # Images, fonts
```

## API Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `POST /api/assistant/chat` | Main chat interface |
| `GET /api/assistant/sessions` | List chat sessions |
| `POST /api/assistant/sessions/{id}/load` | Resume session |
| `GET /api/finance/summary` | Finance overview |
| `GET /api/health/report` | Health data |
| `GET /api/calendar/upcoming` | Calendar events |

## Troubleshooting

### Connection Issues

1. **Check backend is running**:
   ```bash
   curl http://aviraa.duckdns.org:30000/health
   ```

2. **Check port forwarding**:
   - Verify router settings
   - Test from outside network

3. **Check firewall**:
   ```bash
   # On server
   sudo ufw allow 30000/tcp
   ```

### iOS Build Issues

```bash
cd ios
pod deintegrate
pod install
```

### Android Build Issues

```bash
cd android
./gradlew clean
```

## Security Notes

- The app uses HTTP by default for local development
- For production, configure HTTPS with Let's Encrypt
- Sensitive data is automatically masked before external calls
- Session data is stored locally with AsyncStorage

## License

MIT
