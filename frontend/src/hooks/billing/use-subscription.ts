"use client"

import { useQuery } from "@tanstack/react-query"
import { getInvoices, getPlans, getSubscription } from "@/services/billing/billing.service"
import { USE_MOCKS } from "@/lib/mocks"
import { useAuth } from "@/components/providers/auth-provider"

export function useSubscription() {
  // The subscription belongs to a restaurant, so wait until one is active.
  const { activeTenantId } = useAuth()
  return useQuery({
    queryKey: ["billing", "subscription"],
    queryFn: getSubscription,
    enabled: !USE_MOCKS && !!activeTenantId,
    staleTime: 60 * 1000,
  })
}

export function usePlans() {
  const { activeTenantId } = useAuth()
  return useQuery({
    queryKey: ["billing", "plans"],
    queryFn: getPlans,
    enabled: !USE_MOCKS && !!activeTenantId,
    staleTime: 60 * 60 * 1000,
  })
}

export function useInvoices() {
  const { activeTenantId } = useAuth()
  return useQuery({
    queryKey: ["billing", "invoices"],
    queryFn: getInvoices,
    enabled: !USE_MOCKS && !!activeTenantId,
    staleTime: 30 * 1000,
  })
}
