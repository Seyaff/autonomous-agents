"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createTemplate,
  deleteTemplate,
  getOrderUpdates,
  listTemplates,
  setUpOrderUpdates,
  syncTemplates,
  type TemplateDraftPayload,
} from "@/services/templates/templates.service"
import { USE_MOCKS } from "@/lib/mocks"

const KEY = ["templates"] as const

export function useTemplates(status?: string) {
  return useQuery({
    queryKey: [...KEY, status ?? "all"],
    queryFn: () => listTemplates(status),
    enabled: !USE_MOCKS,
  })
}

export function useTemplateActions() {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: KEY })

  return {
    sync: useMutation({ mutationFn: syncTemplates, onSuccess: refresh }),
    create: useMutation({ mutationFn: (payload: TemplateDraftPayload) => createTemplate(payload), onSuccess: refresh }),
    remove: useMutation({
      mutationFn: ({ name, language }: { name: string; language: string }) => deleteTemplate(name, language),
      onSuccess: refresh,
    }),
  }
}

export function useOrderUpdates() {
  const queryClient = useQueryClient()
  const state = useQuery({ queryKey: [...KEY, "order-updates"], queryFn: getOrderUpdates, enabled: !USE_MOCKS })
  const setUp = useMutation({
    mutationFn: (language: string) => setUpOrderUpdates(language),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
  return { state, setUp }
}
