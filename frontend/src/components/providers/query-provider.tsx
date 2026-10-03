"use client"

import { useState } from "react"
import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { toast } from "sonner"

function errorText(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg
  return "Something went wrong. Try again."
}

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  
  const [queryClient] = useState(
    () =>
      new QueryClient({
        // A failed action always says so. Mutations that handle their own error
        // show their own message, so they're left alone here.
        mutationCache: new MutationCache({
          onError: (error, _variables, _context, mutation) => {
            if (mutation.options.onError) return
            toast.error(errorText(error))
          },
        }),
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}