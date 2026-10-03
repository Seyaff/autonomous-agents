"use client"

import { useQuery, type QueryClient } from "@tanstack/react-query"
import { MOCK_KPIS, type KpiValue } from "@/lib/mock/kpis"
import { getDashboardKpis } from "@/services/dashboard/kpis.service"
import { USE_MOCKS } from "@/lib/mocks"

const MOCK_KPIS_KEY = ["mock", "kpis"] as const

export function useMockKpisData() {
  // No `enabled` gate — see use-queue.ts's useMockQueueData for why.
  return useQuery({
    queryKey: MOCK_KPIS_KEY,
    queryFn: async () => MOCK_KPIS,
    staleTime: Infinity,
  })
}

export function incrementMockKpi(queryClient: QueryClient, key: string, delta: number) {
  queryClient.setQueryData<KpiValue[]>(MOCK_KPIS_KEY, (old) =>
    (old ?? []).map((k) => (k.key === key ? { ...k, value: k.value + delta } : k))
  )
}

export function useKpis(needsYouCount: number): { isLoading: boolean; kpis: KpiValue[] } {
  const mock = useMockKpisData()
  const real = useQuery({
    queryKey: ["dashboard", "kpis", "today"],
    queryFn: () => getDashboardKpis("today"),
    enabled: !USE_MOCKS,
  })

  if (USE_MOCKS) {
    return { isLoading: mock.isLoading, kpis: mock.data ?? [] }
  }

  // Server-computed for today (tenant timezone). "Needs you" is live from the
  // queue's own count so the strip and the queue never disagree.
  const kpis: KpiValue[] = [
    { key: "conversations", label: "Chats today", value: real.data?.conversations ?? 0, format: "number" },
    { key: "orders", label: "Orders today", value: real.data?.orders ?? 0, format: "number" },
    { key: "revenue", label: "Revenue today", value: real.data?.revenue ?? 0, format: "currency" },
    { key: "needs_you", label: "Needs you", value: needsYouCount, format: "number" },
  ]

  return { isLoading: real.isLoading, kpis }
}
