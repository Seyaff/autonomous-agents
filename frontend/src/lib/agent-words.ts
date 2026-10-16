// The words the agent shows while it works.

/** Shown while the agent is thinking and hasn't picked a tool yet. One is picked at random every couple of seconds. */
export const THINKING_WORDS = [
  "Thinking",
  "Cooking",
  "Murmuring",
  "Simmering",
  "Brewing",
  "Pondering",
  "Noodling",
  "Percolating",
  "Mulling it over",
  "Marinating",
  "Whisking",
  "Tinkering",
  "Scheming",
  "Connecting dots",
  "Crunching",
  "Untangling",
  "Conjuring",
  "Ruminating",
  "Sleuthing",
  "Puzzling",
  "Stirring the pot",
  "Kneading",
  "Hatching a plan",
  "Doodling",
  "Spelunking",
  "Moseying",
  "Finagling",
  "Wrangling",
  "Vibing",
  "Churning",
]

/** What each tool is doing: shown live (present tense) and once it's finished (past tense). */
const TOOL_STEPS: Record<string, [string, string]> = {
  get_business_settings: ["Reading your settings", "Read your settings"],
  update_business_settings: ["Saving business settings", "Saved business settings"],
  update_reply_settings: ["Tuning how the agent replies", "Tuned the agent's replies"],
  set_agent_enabled: ["Flipping the agent switch", "Checked the agent switch"],
  get_channels: ["Checking WhatsApp and Instagram", "Checked your channels"],
  list_catalog: ["Flipping through the catalog", "Looked through the catalog"],
  set_item_unavailable: ["Updating what's available", "Updated what's available"],
  add_catalog_item: ["Adding to the catalog", "Added to the catalog"],
  update_catalog_item: ["Editing the catalog", "Edited the catalog"],
  remove_catalog_item: ["Preparing the removal", "Prepared the removal"],
  find_orders: ["Rummaging through orders", "Looked through orders"],
  get_order: ["Pulling up the order", "Pulled up the order"],
  update_order_status: ["Moving the order along", "Updated the order"],
  sales_summary: ["Crunching the numbers", "Crunched the numbers"],
  find_customers: ["Looking up customers", "Looked up customers"],
  find_conversations: ["Scanning the inbox", "Scanned the inbox"],
  read_conversation: ["Reading the chat", "Read the chat"],
  message_customer: ["Drafting the message", "Drafted the message"],
  set_chat_handler: ["Handing the chat over", "Handed the chat over"],
  clear_needs_you: ["Clearing the flag", "Cleared the flag"],
  list_templates: ["Checking your templates", "Checked your templates"],
  create_template: ["Drafting a template", "Drafted a template"],
  list_campaigns: ["Checking campaigns", "Checked campaigns"],
  send_campaign: ["Lining up the campaign", "Lined up the campaign"],
  list_forms: ["Checking your forms", "Checked your forms"],
  send_form: ["Preparing the form", "Prepared the form"],
  open_page: ["Opening the page", "Opened the page"],
}

export function toolStep(name: string, done: boolean): string {
  const step = TOOL_STEPS[name]
  if (step) return done ? step[1] : step[0]
  const words = name.replace(/_/g, " ")
  return done ? words : `${words[0]?.toUpperCase() ?? ""}${words.slice(1)}`
}

export function randomThinkingWord(previous?: string): string {
  const pool = THINKING_WORDS.filter((w) => w !== previous)
  return pool[Math.floor(Math.random() * pool.length)]
}
