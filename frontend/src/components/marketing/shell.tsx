import Image from "next/image"
import Link from "next/link"

// Header and footer for the public marketing pages: pricing, how it works, FAQ, features, guides.
export function MarketingHeader() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <Link href="/" className="flex items-center gap-2 font-display text-xl font-semibold">
        <Image src="/brand/logo-light-1024.png" alt="Siyaf logo" width={32} height={32} className="size-8 rounded-md" />
        Siyaf
      </Link>
      <nav className="flex flex-wrap gap-4 text-sm">
        <Link className="underline underline-offset-4" href="/how-it-works">How it works</Link>
        <Link className="underline underline-offset-4" href="/pricing">Pricing</Link>
        <Link className="underline underline-offset-4" href="/guides">Guides</Link>
        <Link className="underline underline-offset-4" href="/faq">FAQ</Link>
        <Link className="underline underline-offset-4" href="/login">Log in</Link>
        <Link className="underline underline-offset-4" href="/signup">Sign up</Link>
      </nav>
    </header>
  )
}

export function MarketingFooter() {
  return (
    <footer className="mt-auto flex flex-wrap gap-4 border-t pt-6 text-sm text-muted-foreground">
      <Link className="underline underline-offset-4" href="/privacy">Privacy policy</Link>
      <Link className="underline underline-offset-4" href="/terms">Terms of service</Link>
      <Link className="underline underline-offset-4" href="/faq">FAQ</Link>
      <span className="ml-auto">Siyaf</span>
    </footer>
  )
}

export function MarketingMain({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-svh w-full max-w-[760px] flex-col gap-10 px-5 py-12 text-foreground">
      {children}
    </main>
  )
}

export function CallToAction({ text, href = "/signup" }: { text: string; href?: string }) {
  return (
    <div className="rounded-lg border p-5">
      <Link href={href} className="inline-block rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background">
        {text}
      </Link>
    </div>
  )
}
