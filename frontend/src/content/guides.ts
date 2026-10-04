// Guides for the public site. Each one answers a question an owner asks.
// A figure that depends on Meta's current prices says so, and must be checked before it's published.

export type Guide = {
  slug: string
  title: string
  description: string
  date: string
  updated: string
  keywords: string[]
  intro: string
  sections: { heading: string; body: string[] }[]
  related: string[]
  // Held back until its figures are confirmed on Meta's current rate card. Hidden from the index, sitemap and routes.
  draft?: boolean
}

export const GUIDES: Guide[] = [
  {
    slug: "whatsapp-business-api-pricing-pakistan",
    draft: true,
    title: "WhatsApp Business API pricing in Pakistan",
    description: "How WhatsApp Business API fees work for a restaurant in Pakistan: the free replies, the fee after them, and a worked example.",
    date: "2026-10-04",
    updated: "2026-10-04",
    keywords: ["whatsapp business api pricing pakistan", "whatsapp business api cost"],
    intro: "WhatsApp fees changed recently, and most restaurant owners we talk to aren't sure what they now pay. This guide explains it in plain terms.",
    sections: [
      {
        heading: "Who pays what",
        body: [
          "Meta charges your business for the WhatsApp messages you send through the API. Siyaf charges for the agent that answers your customers. The two bills are separate.",
          "Meta includes a number of free replies each month. Replies after that are charged per reply.",
        ],
      },
      {
        heading: "A worked example",
        body: [
          "Say a restaurant sends 1,800 replies in a month. The first 1,000 are free. The next 800 are charged at Meta's per-reply rate for Pakistan. At Rs 4.2 per reply, that's about Rs 3,360 in Meta fees for the month, on top of the Siyaf plan.",
          "Your own numbers will differ. Count your replies for a typical month before you decide.",
        ],
      },
      {
        heading: "Check the current figures",
        body: [
          "Meta changes its prices. The rate Meta charges on the day you read this is the one that counts. Check Meta's current price list for WhatsApp Business messaging in Pakistan before you decide.",
        ],
      },
    ],
    related: ["take-restaurant-orders-on-whatsapp", "whatsapp-business-app-vs-api"],
  },
  {
    slug: "take-restaurant-orders-on-whatsapp",
    title: "How to take restaurant orders on WhatsApp",
    description: "Three ways restaurants take orders on WhatsApp: by hand, with the WhatsApp Business app, or with an AI agent. What each one is good for.",
    date: "2026-10-04",
    updated: "2026-10-04",
    keywords: ["how to take restaurant orders on whatsapp", "whatsapp food ordering"],
    intro: "Most restaurants in Pakistan already take orders on WhatsApp, one message at a time. There are three common ways to do it, and each suits a different kind of restaurant.",
    sections: [
      {
        heading: "1. By hand",
        body: ["A person reads each message and replies. It costs nothing extra, but it depends on someone being free, and orders at busy times get missed."],
      },
      {
        heading: "2. With the WhatsApp Business app",
        body: ["The app gives you a catalogue, quick replies and away messages. It's free, and it's good for a small menu. It still needs someone to reply to each customer."],
      },
      {
        heading: "3. With an AI agent",
        body: [
          "An agent answers customers at any hour, knows your menu and hours, and takes the order. The customer confirms it before it reaches the kitchen. You still take over any conversation yourself.",
          "An agent costs a monthly fee. It's worth most to restaurants that miss orders because nobody is free to reply.",
        ],
      },
    ],
    related: ["whatsapp-business-api-pricing-pakistan", "whatsapp-business-app-vs-api"],
  },
  {
    slug: "whatsapp-business-app-vs-api",
    title: "WhatsApp Business app vs the WhatsApp Business API",
    description: "The difference between the WhatsApp Business app and the WhatsApp Business API, and when a restaurant needs the API.",
    date: "2026-10-04",
    updated: "2026-10-04",
    keywords: ["whatsapp business app vs api", "whatsapp business api for restaurants"],
    intro: "The WhatsApp Business app and the WhatsApp Business API look similar, but they're for different jobs. Choosing the wrong one wastes time.",
    sections: [
      {
        heading: "The app",
        body: ["The app runs on a phone. One person replies from it. It's free, and it suits a small shop that answers its own messages."],
      },
      {
        heading: "The API",
        body: [
          "The API lets software send and receive messages for your number. An agent, a shared inbox or an automatic reply needs the API. It's the route for a restaurant with several staff or a lot of orders.",
        ],
      },
      {
        heading: "Moving a number",
        body: ["Moving a number from the app to the API can mean losing its chat history on the phone. Export what you need first, and follow Meta's current steps for moving a number."],
      },
    ],
    related: ["set-up-whatsapp-business-api-restaurant", "take-restaurant-orders-on-whatsapp"],
  },
  {
    slug: "set-up-whatsapp-business-api-restaurant",
    title: "How to set up the WhatsApp Business API for a restaurant",
    description: "The steps to set up the WhatsApp Business API for a restaurant: a Meta account, a business verification, and a number that's ready to use.",
    date: "2026-10-04",
    updated: "2026-10-04",
    keywords: ["how to set up whatsapp business api", "whatsapp business api setup restaurant"],
    intro: "Setting up the API takes a few steps and some waiting for Meta's checks. Here is the order to do them in.",
    sections: [
      {
        heading: "1. A Meta business account",
        body: ["Create a business account in Meta Business Manager, with your business name as it appears on your registration documents."],
      },
      {
        heading: "2. Business verification",
        body: ["Meta asks for documents to confirm the business. This can take several days, so start early."],
      },
      {
        heading: "3. A number",
        body: ["Meta sets the rules for which numbers can be used, and they change. Check the current rules first. The number must be able to receive an SMS or a call for verification."],
      },
      {
        heading: "4. Connect it to the agent",
        body: ["Once the number is verified, connect it in Siyaf's Settings, with the Meta popup or by entering the number's details."],
      },
    ],
    related: ["whatsapp-business-app-vs-api", "whatsapp-business-api-pricing-pakistan"],
  },
]

export const PUBLISHED_GUIDES = GUIDES.filter((g) => !g.draft)

export function guideBySlug(slug: string): Guide | undefined {
  return PUBLISHED_GUIDES.find((g) => g.slug === slug)
}
