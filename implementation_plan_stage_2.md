# Implementation Plan: Conversational AI Optimization & Operational Enhancements

Enhancing the autonomous restaurant platform to resolve order memory loss, enable WhatsApp PDF/media document ingestion, adapt language and currency to Pakistani hospitality standards (Roman Urdu & PKR/Rs.), and introduce a psychological sales closing funnel with strategic interactive checkout buttons.

---

## 1. Key Problems & Solutions

### 1.1. Persistent Order Memory Loss
- **Problem**: When a customer places an order and returns 10 minutes later asking for confirmation or status, the agent says *"I don't see any order in the system"* because checkout emptied the in-memory cart and the LLM had no access to query past database orders.
- **Solution**:
  1. On every inbound WhatsApp message from a phone number, query the database for the customer's active/recent order (`status IN ('confirmed', 'preparing', 'out_for_delivery')`).
  2. Inject active order details directly into the agent's context (`ACTIVE ORDER #... placed at ... total Rs. ...`).
  3. Add an automated status notification pipeline (`PATCH /api/v1/orders/{order_id}/status`) so when the kitchen/rider marks an order `preparing`, `out_for_delivery`, or `delivered`, the customer receives an automatic WhatsApp ping!

### 1.2. WhatsApp Media & PDF Menu Ingestion
- **Problem**: When a restaurant owner sends a menu PDF or business document on WhatsApp, the bot replies *"I did not receive PDF"* because Meta delivers media as an ID (`messages[0].document.id`), which must be resolved and downloaded via Meta Graph API.
- **Solution**:
  1. Update `app/services/whatsapp_service.py` with `download_media(media_id)`.
  2. In `app/api/v1/webhooks_whatsapp.py`, detect `msg_type in ["document", "image"]`.
  3. Fetch the media download URL from Meta (`GET https://graph.facebook.com/v21.0/{media_id}`), stream the file bytes with bearer authentication, and pass them to `process_owner_inventory_message(document_bytes=...)`.
  4. Parse with `menu_parser_service` and auto-populate the restaurant catalog.

### 1.3. Language, Cultural Hospitality & Currency (Roman Urdu & PKR)
- **Problem**: The bot spoke generic English with dollar prices (`$`), feeling foreign for a Pakistani restaurant.
- **Solution**:
  1. Update default currency to **PKR (Rs.)** across database models and seed data.
  2. System prompt rewritten for authentic Pakistani hospitality in **Roman Urdu** (e.g., *"Assalam-o-Alaikum! Da Pakhtun Dera mein khushamdeed..."*, *"Aap kitne afraad (people) ke liye order kar rahe hain?"*).
  3. Dynamically adapts: If the customer writes in English, reply in English; if in Roman Urdu, reply in Roman Urdu.

### 1.4. Psychological Sales Closing Funnel (No Huge Menu Dumping)
- **Problem**: Bot was dumping a massive list of all dishes on the first message, overwhelming the customer.
- **Solution**:
  - **Turn 1 (Warm Greeting & Qualification)**: Welcome the customer and ask party size / craving: *"Kitne afraad ke liye order tayyar karwayein? Aur aaj Karahi ka mood hai ya BBQ / Pulao?"*
  - **Turn 2 (Curated Recommendations)**: Present only top 2-3 dishes matching their craving with portion advice.
  - **Turn 3 (Smooth Close & Address)**: Gather address and confirm cart.

### 1.5. Natural Human Feel with Strategic Interactive Buttons
- **Problem**: Too many robotic buttons everywhere ruins the personal hospitality feel.
- **Solution**: Keep the whole dialogue conversational and human. Send WhatsApp interactive quick-reply buttons **ONLY** at the final order confirmation step (`[✅ Confirm Order]`, `[✏️ Change Cart]`).

---

## 2. Proposed Code Changes

### [Component: WhatsApp Media & Service Layer]
#### [MODIFY] [app/services/whatsapp_service.py](file:///c:/Users/AGP%20KOHAT/Desktop/autonomous-agents/app/services/whatsapp_service.py)
- Add `download_media_bytes(media_id)` to query Meta Graph API media endpoint and download raw file content.

### [Component: Webhook & Media Routing Layer]
#### [MODIFY] [app/api/v1/webhooks_whatsapp.py](file:///c:/Users/AGP%20KOHAT/Desktop/autonomous-agents/app/api/v1/webhooks_whatsapp.py)
- Detect `document` and `image` types in Meta incoming webhook.
- Download media using `whatsapp_service.download_media_bytes`.
- Route downloaded document directly to `process_owner_inventory_message(document_bytes=...)`.
- Automatically query active orders for the sender phone number and pass to agent.

### [Component: Customer Support & Sales Agent]
#### [MODIFY] [app/agents/tenant/customer_support/prompts.py](file:///c:/Users/AGP%20KOHAT/Desktop/autonomous-agents/app/agents/tenant/customer_support/prompts.py)
- System prompt rewritten in natural Roman Urdu / English hospitality tone.
- 3-step sales qualification guidelines (party size $\rightarrow$ curated recommendations $\rightarrow$ close).
- Instructions for currency in **Rs. / PKR**.

#### [MODIFY] [app/agents/tenant/customer_support/graph.py](file:///c:/Users/AGP%20KOHAT/Desktop/autonomous-agents/app/agents/tenant/customer_support/graph.py)
- Inject active database order history into context so the agent never forgets a placed order.
- Send interactive buttons only at final checkout step.

### [Component: Orders & Delivery Notification Endpoint]
#### [MODIFY] [app/api/v1/orders.py](file:///c:/Users/AGP%20KOHAT/Desktop/autonomous-agents/app/api/v1/orders.py)
- When order status is updated (e.g. `preparing`, `out_for_delivery`, `delivered`), automatically send WhatsApp status notification to customer.

---

## 3. Verification Plan

### Automated Tests
- `pytest tests/test_core.py -v`: Verify all existing tests pass with updated currency and routes.
- Add test verifying active order database injection.

### WhatsApp Real Device Verification
1. Text *"Hi"* $\rightarrow$ Verify warm Roman Urdu greeting with qualifying party size question.
2. Text *"3 logon ke liye Karahi chahiye"* $\rightarrow$ Verify agent recommends 2-3 specific dishes with portion guidance in Rs. (no huge menu dump).
3. Place order $\rightarrow$ Receive interactive confirmation button.
4. Wait / Text 10 minutes later: *"Mera order kahan pohancha?"* $\rightarrow$ Verify agent immediately recalls order number and preparation status!
5. Send PDF menu file as owner $\rightarrow$ Verify file is downloaded, parsed, and catalog is updated.
