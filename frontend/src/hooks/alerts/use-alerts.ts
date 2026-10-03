"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { listAlerts, markAllAlertsRead, markAlertRead } from "@/services/alerts/alerts.service"

export const ALERTS_KEY = ["alerts"] as const

/** The owner's alerts. The websocket refreshes this when something new happens,
 * and the list is also polled, so nothing is missed if the socket drops. */
export function useAlerts(enabled: boolean) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ALERTS_KEY,
    queryFn: listAlerts,
    enabled,
    refetchInterval: 60_000,
  })

  const readOne = useMutation({
    mutationFn: markAlertRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ALERTS_KEY }),
  })

  const readAll = useMutation({
    mutationFn: markAllAlertsRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ALERTS_KEY }),
  })

  return { query, readOne, readAll }
}
