// Every real user of this app lands in either /founder or /dashboard —
// <AuthProvider> redirects away from "/" as soon as the session loads. This
// stays only as a neutral splash for that brief moment (and as the route
// Next.js requires to exist at "/").
export default function RootPage() {
  return (
    <div className="flex min-h-svh items-center justify-center bg-background">
      <div className="size-6 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-foreground" />
    </div>
  )
}
