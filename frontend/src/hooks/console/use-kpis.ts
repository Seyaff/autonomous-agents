"use client"

import { useQuery, type QueryClient } from "@tanstack/react-query"
import { MOCK_KPIS, type KpiValue } from "@/lib/mock/kpis"
import { use7DaySummary } from "@/hooks/analytics/use-7day-summary"
import { useOrderStats } from "@/hooks/orders/use-order-stats"
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
  const analytics = use7DaySummary({ enabled: !USE_MOCKS })
  const orderStats = useOrderStats({ enabled: !USE_MOCKS })

  if (USE_MOCKS) {
    return { isLoading: mock.isLoading, kpis: mock.data ?? [] }
  }

  const kpis: KpiValue[] = [
    {
      key: "conversations",
      label: "Conversations",
      value: analytics.data?.total_conversations ?? 0,
      format: "number",
    },
    { key: "orders", label: "Orders", value: orderStats.data?.total_orders ?? 0, format: "number" },
    { key: "revenue", label: "Revenue", value: orderStats.data?.total_revenue ?? 0, format: "currency" },
    { key: "needs_you", label: "Needs you", value: needsYouCount, format: "number" },
  ]

  return { isLoading: analytics.isLoading || orderStats.isLoading, kpis }
}
