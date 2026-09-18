# Frontend Architecture & Design Specification (Next.js 15)

This folder is reserved for the Next.js 15 frontend application. It follows a **Linear / Apple-inspired Dark Luxury aesthetic** designed for maximum conversion and owner delight.

---

## 1. Design System & Aesthetic Tokens

### 1.1. Color Palette (Obsidian & Platinum Luxury)
- **Canvas / Background**: `#09090b` (Deep Obsidian / Zinc 950)
- **Card Surface**: `#121215` (Subtle elevated charcoal) with `backdrop-blur-md`
- **Hairline Borders**: `rgba(255, 255, 255, 0.08)` (`border-white/10`)
- **Primary Typography**: `#f4f4f5` (Zinc 100 — crisp, legible)
- **Muted Typography**: `#71717a` (Zinc 500 — subtle, secondary)
- **Brand Accents**:
  - Emerald Live Glow: `#10b981` (for active orders, live kitchen states)
  - Amber Warmth: `#f59e0b` (for kitchen preparation alerts)
- **Strict Rule**: No chaotic rainbow gradients or loud saturated colors. Only subtle, ambient glows and monochromatic elegance.

### 1.2. Typography Hierarchy
- **Font Family**: `Inter` / `Geist` or `SF Pro Display`
- **Headings**: Semibold / Medium with `-0.02em` tight letter-spacing
- **Numbers & Metrics**: Monospaced tabular numerals (`font-mono tracking-tight`)

---

## 2. Meta Embedded Signup Frontend Integration

In Next.js, restaurant owners onboard with 1 click without entering any API keys:

```tsx
// Example integration for Next.js with Meta Facebook SDK
declare global {
  interface Window {
    FB: any;
  }
}

export function ConnectWhatsAppButton({ tenantId, onConnected }: { tenantId: string; onConnected: () => void }) {
  const handleConnect = () => {
    window.FB.login(
      function (response: any) {
        if (response.authResponse?.code) {
          // Send temporary OAuth code to backend
          fetch(`/api/v1/onboarding/${tenantId}/whatsapp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: response.authResponse.code }),
          }).then(() => onConnected());
        }
      },
      {
        config_id: process.env.NEXT_PUBLIC_META_CONFIG_ID, // Your Meta Embedded Signup Configuration ID
        response_type: 'code',
        override_default_response_type: true,
        extras: {
          setup: {},
          featureType: '',
          sessionInfoVersion: '2',
        },
      }
    );
  };

  return (
    <button
      onClick={handleConnect}
      className="h-11 px-6 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-all shadow-[0_0_20px_rgba(16,185,129,0.2)]"
    >
      Connect WhatsApp Business
    </button>
  );
}
```

---

## 3. Onboarding Steps & API Contract

### Step 1: Brand & Identity
- **Endpoint**: `PATCH /api/v1/onboarding/{tenant_id}/identity`
- **Inputs**: Name, Cuisine, Address, Operating Hours, Currency (PKR).

### Step 2: Menu Ingestion
- **Endpoint**: `POST /api/v1/onboarding/{tenant_id}/menu`
- **Inputs**: Drag-and-drop PDF / image menu or quick JSON dishes.

### Step 3: Meta Embedded Signup
- **Endpoint**: `POST /api/v1/onboarding/{tenant_id}/whatsapp`
- **Inputs**: Temporary Meta authorization code.

### Step 4: Kitchen Line Verification
- **Endpoint**: `POST /api/v1/onboarding/{tenant_id}/test-kitchen`
- **Inputs**: Kitchen staff WhatsApp number. Fires a live test ticket immediately.

### Step 5: Complete & Launch
- **Endpoint**: `POST /api/v1/onboarding/{tenant_id}/complete`
- **Output**: Public `wa.me` customer ordering link and table QR code.

---

## 4. Kitchen Display System (KDS) WebSockets

- **Connection**: `ws://<host>/api/v1/ws/orders/{tenant_id}`
- **Events**:
  - `ORDER_CREATED`: New order arrives (triggers gentle audio chime).
  - `STATUS_UPDATED`: Order moves between `preparing`, `out_for_delivery`, `delivered`.
