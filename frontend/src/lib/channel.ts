import type { Conversation } from "@/services/inbox/inbox.service"

type ChannelFields = Pick<Conversation, "customer_phone" | "channel" | "customer_username">

export function isInstagram(c: ChannelFields): boolean {
  return c.channel === "instagram" || c.customer_phone.startsWith("ig:")
}

/** How to reach the customer, as the owner reads it: a phone number, or an Instagram handle. */
export function contactLabel(c: ChannelFields): string {
  if (!isInstagram(c)) return c.customer_phone
  return c.customer_username ? `@${c.customer_username} on Instagram` : "Instagram customer"
}
