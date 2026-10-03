"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { generateWeeklyReport, listWeeklyReports } from "@/services/reports/reports.service"
import { USE_MOCKS } from "@/lib/mocks"

const KEY = ["analytics", "weekly-reports"] as const

export function useWeeklyReports() {
  const queryClient = useQueryClient()
  const list = useQuery({
    queryKey: KEY,
    queryFn: listWeeklyReports,
    enabled: !USE_MOCKS,
  })

  const generate = useMutation({
    mutationFn: generateWeeklyReport,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })

  return { list, generate }
}
