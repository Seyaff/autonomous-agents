// Facts used across the marketing pages. Prices and limits come from PRICING.md.
// Change them here, and every page and structured-data block follows.

export const PLANS = [
  { key: "basic", name: "Basic", priceMonthly: 2999, priceYearly: 29990, chats: 200 },
  { key: "standard", name: "Standard", priceMonthly: 5999, priceYearly: 59990, chats: 600 },
  { key: "pro", name: "Pro", priceMonthly: 11999, priceYearly: 119990, chats: 1500 },
] as const

export const EXTRA_CHAT_PKR = 3
export const TRIAL_DAYS = 14
export const TRIAL_CHAT_CAP = 100

// A "chat" is one customer conversation the agent replied in during the month. A busy chat counts once.
export const CHAT_DEFINITION =
  "One AI chat is one customer conversation that the agent replied in during the month. A busy conversation counts once."

// Meta's WhatsApp fees are billed by Meta to the restaurant, not by Siyaf. Check Meta's current price list before publishing any figure.
export const META_FEE_NOTE =
  "WhatsApp message fees are billed by Meta to your business, not by Siyaf. Siyaf doesn't add or resell them. Check Meta's current price list for the exact figures."

export const FAQS: { q: string; a: string }[] = [
  {
    q: "What does Siyaf do?",
    a: "Siyaf answers your restaurant's customers on WhatsApp. It knows your menu, opening hours and delivery areas, takes orders, and hands over to you when a customer needs a person.",
  },
  {
    q: "Does the agent send an order to my kitchen without the customer agreeing?",
    a: "No. The customer reviews the order summary and taps Confirm first. Only then does the order go to the restaurant.",
  },
  {
    q: "Can the agent understand Urdu?",
    a: "Yes. It replies in English or Roman Urdu, and it understands voice notes in Urdu. Replies match the way the customer writes.",
  },
  {
    q: "How long is the free trial?",
    a: `The trial lasts ${TRIAL_DAYS} days and allows up to ${TRIAL_CHAT_CAP} AI chats. No payment is needed to start.`,
  },
  {
    q: "What is an AI chat?",
    a: CHAT_DEFINITION,
  },
  {
    q: "Do I need a new WhatsApp number?",
    a: "Meta sets the rules for which numbers can be used with the WhatsApp API, and they change. Check the current rules before you start. Moving an existing number can mean losing its chat history.",
  },
  {
    q: "Who pays for WhatsApp messages?",
    a: META_FEE_NOTE,
  },
  {
    q: "Can I take over a conversation myself?",
    a: "Yes. You can take over any chat, reply yourself, and hand it back to the agent.",
  },
  {
    q: "Can I cancel?",
    a: "Yes. Cancelling keeps everything working until the end of the period you've paid for. You can cancel from the Billing page.",
  },
]
