import Link from "next/link"

// The public homepage. Anyone can read it without signing in: what Siyaf is, who it's for,
// and links to the privacy policy and terms.
export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-svh max-w-[760px] flex-col gap-10 px-5 py-12 text-foreground">
      <header className="flex items-center justify-between">
        <span className="font-display text-xl font-semibold">Siyaf</span>
        <nav className="flex gap-3 text-sm">
          <Link className="underline underline-offset-4" href="/login">Log in</Link>
          <Link className="underline underline-offset-4" href="/signup">Sign up</Link>
        </nav>
      </header>

      <section className="space-y-4">
        <h1 className="font-display text-3xl font-semibold leading-tight">
          An AI agent that answers your restaurant's WhatsApp customers.
        </h1>
        <p className="text-base text-muted-foreground">
          Siyaf answers customers on WhatsApp in your restaurant's own voice. It knows your menu, your
          opening hours and your delivery areas. It takes orders, and it only sends an order to your kitchen
          after the customer confirms it. It hands over to you when a customer needs a person.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/signup" className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background">
            Start a free trial
          </Link>
          <Link href="/login" className="rounded-md border px-4 py-2 text-sm font-medium">
            Log in
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {[
          ["Your menu", "Upload your menu once. The agent answers from your dish list, with prices, and you can hide or sell out dishes."],
          ["Orders you can trust", "Customers confirm their order before it reaches the kitchen. You see every order in one place."],
          ["You stay in charge", "Take over any chat, see what the agent remembers, and choose which alerts reach your WhatsApp."],
        ].map(([title, body]) => (
          <div key={title} className="rounded-lg border p-4">
            <h2 className="font-medium">{title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{body}</p>
          </div>
        ))}
      </section>

      <section className="space-y-2 text-sm text-muted-foreground">
        <p>
          Siyaf is for restaurant owners. Plans start at Rs 2,999 a month after a 14-day free trial. Meta bills
          WhatsApp message fees to your business directly.
        </p>
      </section>

      <footer className="mt-auto flex gap-4 border-t pt-6 text-sm text-muted-foreground">
        <Link className="underline underline-offset-4" href="/privacy">Privacy policy</Link>
        <Link className="underline underline-offset-4" href="/terms">Terms of service</Link>
        <span className="ml-auto">Siyaf</span>
      </footer>
    </main>
  )
}
