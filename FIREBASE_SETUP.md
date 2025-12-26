# Firebase Service Account Setup

## ⚠️ IMPORTANT: Required for Phone Authentication

To enable phone authentication, you need to add the Firebase service account JSON file.

### Steps:

1. Go to [Firebase Console → Project Settings → Service Accounts](https://console.firebase.google.com/project/real-33816464-5a38c/settings/serviceaccounts/adminsdk)

2. Click "Generate new private key"

3. Download the JSON file

4. Save it as `firebase-service-account.json` in this directory (`backend/`)

5. **NEVER commit this file to git** (it's already in `.gitignore`)

### File Location:
```
backend/
├── app/
├── firebase-service-account.json  ← Place the file here
└── requirements.txt
```

### Verification:
Once added, restart the backend:
```bash
docker-compose restart backend
```

You should see: `✅ Firebase Admin SDK initialized` in the logs.

### Without This File:
- Phone authentication will not work
- Users will see an error when trying to login with phone
- Email/password login will still work
