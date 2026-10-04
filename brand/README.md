# Siyaf brand kit

The logo is the founder's portrait in black ink line art, inside a black square frame. Two colours only: ink `#0b0b0c` and white.

- **Large uses** (over 64px) show the full portrait.
- **Small uses** (favicons, app icons, the Google sign-in logo) use a tight crop of the face, because the full portrait turns to mush below about 64px.

Source: `brand/portrait-draft.jpg`. When the final portrait (with the button-up shirt) arrives, regenerate this kit from it.

## Files

All files are in `brand/kit/`.

| File | Size | Use it for |
|---|---|---|
| `logo-light-1024.png` | 1024×1024 | Main logo on light backgrounds |
| `logo-dark-1024.png` | 1024×1024 | Main logo on dark backgrounds (same drawing, with a white edge) |
| `face-light-512.png` | 512×512 | Small square icon on light backgrounds |
| `face-dark-512.png` | 512×512 | Small square icon on dark backgrounds |
| `favicon.ico` | 16, 32, 48 | Browser tab |
| `icon-32.png` | 32×32 | PNG favicon |
| `apple-touch-icon.png` | 180×180 | iPhone home screen |
| `icon-192.png`, `icon-512.png` | 192, 512 | Android home screen and installed web app |
| `maskable-512.png` | 512×512 | Android adaptive icon (safe area padded) |
| `site.webmanifest` | | Web app manifest that points at the icons above |
| `og-image-1200x630.png` | 1200×630 | Link previews on WhatsApp, LinkedIn, X, Slack |
| `google-oauth-logo-120.png` | 120×120 | Google sign-in consent screen |
| `meta-app-icon-1024.png` | 1024×1024 | Meta developer app icon |
| `whatsapp-profile-640.png` | 640×640 | WhatsApp Business profile photo |
| `linkedin-profile-400.png` | 400×400 | LinkedIn profile or company logo |
| `linkedin-banner-1584x396.png` | 1584×396 | LinkedIn personal profile banner |
| `x-profile-400.png` | 400×400 | X profile picture |

## Where each one goes

### Frontend (Next.js, `frontend/`)
- Next.js reads icons from the `app` folder automatically:
  - copy `favicon.ico` to `src/app/favicon.ico`, replacing the default
  - copy `icon-512.png` to `src/app/icon.png`
  - copy `apple-touch-icon.png` to `src/app/apple-icon.png`
  - copy `og-image-1200x630.png` to `src/app/opengraph-image.png`
- Copy the rest of `brand/kit/` to `public/brand/`, and `site.webmanifest` to `public/site.webmanifest`.
- In `src/app/layout.tsx`, set `metadata`:
  - `title: "Siyaf"`
  - `description: "AI that answers your restaurant's WhatsApp and takes orders."`
  - `manifest: "/site.webmanifest"`
  - `themeColor` (or the `viewport` export): `#0b0b0c`
- Use `logo-light-1024.png` (via `next/image`, at 32–40px) in the sidebar, the setup dialogs and the landing page nav.

### Google Cloud Console (Google sign-in)
- **APIs & Services → OAuth consent screen → Branding:**
  - App name: Siyaf
  - App logo: `google-oauth-logo-120.png` (Google wants 120×120, under 1 MB)
  - add your app domain, privacy policy and terms URLs
- Adding a logo can send the app through Google's brand verification. Do it once the domain and privacy page are live.

### Meta (WhatsApp)
- **developers.facebook.com → your app → App settings → Basic → App icon:** `meta-app-icon-1024.png`
- **WhatsApp Manager → Phone numbers → Profile:** profile photo `whatsapp-profile-640.png`, display name Siyaf, plus a short description and website. WhatsApp shows the photo as a circle, so check that the face isn't cut off.

### Social profiles
- **LinkedIn:** `linkedin-profile-400.png` as the photo or company logo, `linkedin-banner-1584x396.png` as the banner
- **X:** `x-profile-400.png`
- **Gmail** (the address that sends owner alerts): set the account photo to `linkedin-profile-400.png`, so emails show the logo

### Render (backend)
Render has nothing to brand. The API serves no pages.
