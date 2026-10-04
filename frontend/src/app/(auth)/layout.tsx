import type { Metadata } from "next"

// Sign-in and sign-up pages are for people who already have an account. Keep them out of search.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
