// Feature pages. Each one answers one search. Only describes what the product does today.

export type FeaturePage = {
  slug: string
  title: string
  description: string
  heading: string
  intro: string
  points: { title: string; text: string }[]
}

export const FEATURES: FeaturePage[] = [
  {
    slug: "whatsapp-order-taking",
    title: "WhatsApp order taking for restaurants",
    description: "Take restaurant orders on WhatsApp around the clock. The agent reads the menu, builds the order, and sends it to your kitchen once the customer confirms.",
    heading: "WhatsApp order taking for restaurants",
    intro: "Customers message your WhatsApp number. The agent answers from your menu and hours, takes the order, and asks the customer to confirm it with a tap.",
    points: [
      {
        title: "Orders taken in chat",
        text: "The agent asks what the customer wants, which dishes, how many, and where to deliver. It only offers dishes that are on the menu and available.",
      },
      {
        title: "Button confirmation",
        text: "The customer sees a summary with Confirm and Cancel buttons. The order goes to the kitchen only after Confirm.",
      },
      {
        title: "Sent to the kitchen",
        text: "Confirmed orders appear on your dashboard with their status, so you can track them from new to delivered.",
      },
      {
        title: "Sold-out dishes",
        text: "Mark a dish as sold out and the agent stops offering it straight away.",
      },
    ],
  },
  {
    slug: "roman-urdu-and-voice-notes",
    title: "WhatsApp bot that understands Urdu",
    description: "A WhatsApp ordering agent that replies in English or Roman Urdu and understands Urdu voice notes, so customers can order the way they already talk.",
    heading: "A WhatsApp agent that understands Urdu",
    intro: "Many customers write in Roman Urdu, and many send voice notes. The agent handles both.",
    points: [
      {
        title: "Replies in English or Roman Urdu",
        text: "The agent replies in the language the customer writes in, English or Roman Urdu.",
      },
      {
        title: "Understands voice notes",
        text: "A voice note is transcribed and handled like a typed message. The customer doesn't need to type the order.",
      },
    ],
  },
]

export function featureBySlug(slug: string): FeaturePage | undefined {
  return FEATURES.find((f) => f.slug === slug)
}
