# Meta OAuth Configuration for WhatsApp Embedded Signup

## Overview
This document describes the exact values to configure in Meta Developer Dashboard for the WhatsApp Embedded Signup flow.

---

## App Settings → Basic

| Field | Value |
|-------|-------|
| **App Name** | Your app name (e.g., "Siyaf Restaurant AI") |
| **App Domain** | `siyaf.vercel.app` |
| **Privacy Policy URL** | `https://siyaf.vercel.app/privacy` |
| **Terms of Service URL** | `https://siyaf.vercel.app/terms` |
| **App Icon** | Upload your logo (1024x1024) |

---

## WhatsApp → Configuration

### 1. Redirect URI to check
This is used by Meta to validate redirect URIs during the Embedded Signup flow.

```
https://siyaf.onrender.com/api/v1/auth/google/callback
```

> **Note**: This should match your `GOOGLE_CALLBACK_URL` environment variable (used for Google OAuth, but Meta also validates this pattern).

### 2. Valid OAuth Redirect URIs
These are the exact URIs Meta will redirect to after user authorization.

```
https://siyaf.onrender.com/api/v1/auth/google/callback
https://siyaf.vercel.app/api/auth/google/callback
http://localhost:8000/api/v1/auth/google/callback
http://localhost:3000/api/auth/google/callback
```

> **Important**: 
> - Include both production (Vercel/Render) and local development URLs
> - The `/api/auth/google/callback` path is used by our backend for the Meta Embedded Signup flow (reuses the same callback endpoint)

---

## Meta Login → Settings (for JavaScript SDK)

### 3. Allowed Domains for the JavaScript SDK
These domains are allowed to load and initialize the Meta SDK (`FB.init()`).

```
siyaf.vercel.app
localhost
```

> **Format**: One domain per line, no protocol, no path
> - Do NOT include `https://` or `http://`
> - Do NOT include trailing slashes

---

## WhatsApp → Configuration → Webhooks (Optional - for production)

### 4. Deauthorize Callback URL
Called when a user removes your app from their WhatsApp Business Account.

```
https://siyaf.onrender.com/api/v1/whatsapp/deauthorize
```

> **Note**: You'll need to implement this endpoint if you want to handle deauthorization events.

---

## Environment Variables Required

### Backend (Render)
```bash
META_APP_ID=your_meta_app_id
META_APP_SECRET=your_meta_app_secret
META_CONFIG_ID=your_meta_config_id  # From Embedded Signup setup
WHATSAPP_VERIFY_TOKEN=your_verify_token
WHATSAPP_TOKEN=your_whatsapp_access_token  # Permanent token after Embedded Signup
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_BUSINESS_ACCOUNT_ID=your_waba_id
GOOGLE_CALLBACK_URL=https://siyaf.onrender.com/api/v1/auth/google/callback
FRONTEND_URL=https://siyaf.vercel.app
```

### Frontend (Vercel)
```bash
NEXT_PUBLIC_BACKEND_URL=https://siyaf.onrender.com/api/v1
NEXT_PUBLIC_META_APP_ID=your_meta_app_id
META_CONFIG_ID=your_meta_config_id
```

---

## Embedded Signup Flow

1. **User clicks "Connect WhatsApp"** on onboarding step 4
2. **Frontend** calls `/api/auth/google?next=/onboarding` (proxied to backend)
3. **Backend** initiates Meta OAuth with `redirect_uri` = `GOOGLE_CALLBACK_URL`
4. **Meta** shows Embedded Signup popup (user selects WABA, phone number)
5. **Meta redirects** to `GOOGLE_CALLBACK_URL` with `code` and `state`
6. **Backend** exchanges `code` for access token, stores WABA info
7. **Backend** redirects to frontend `next` URL (e.g., `/onboarding`)
8. **Frontend** completes onboarding

---

## Testing Checklist

- [ ] Meta App is in **Live** mode (not Development)
- [ ] WhatsApp product is **added** to the app
- [ ] **Embedded Signup** is configured in WhatsApp → Configuration
- [ ] All redirect URIs match exactly (including trailing slashes)
- [ ] JavaScript SDK domains include `siyaf.vercel.app`
- [ ] `META_APP_ID` and `META_APP_SECRET` are set in both frontend and backend
- [ ] Test with a real Meta Business Manager account

---

## Common Issues

| Issue | Solution |
|-------|----------|
| "Invalid redirect URI" | Ensure exact match in Valid OAuth Redirect URIs |
| "Domain not allowed" | Add `siyaf.vercel.app` to Allowed Domains for JavaScript SDK |
| "App not verified" | Submit for Meta review or use test users |
| "Invalid META_CONFIG_ID" | Get config ID from WhatsApp → Embedded Signup setup |
| Popup blocked | Ensure popup is triggered by user click (not auto) |

---

## References

- [Meta Embedded Signup Docs](https://developers.facebook.com/docs/whatsapp/embedded-signup)
- [WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Meta Login for JavaScript SDK](https://developers.facebook.com/docs/facebook-login/web)