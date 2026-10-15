"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createForm,
  deleteForm,
  listFormResponses,
  listForms,
  publishForm,
  updateForm,
  type FormDraftPayload,
} from "@/services/forms/forms.service"
import { USE_MOCKS } from "@/lib/mocks"

const KEY = ["forms"] as const

export function useForms() {
  return useQuery({ queryKey: KEY, queryFn: listForms, enabled: !USE_MOCKS })
}

export function useFormResponses(formId: string | null) {
  return useQuery({
    queryKey: [...KEY, formId, "responses"],
    queryFn: () => listFormResponses(formId as string),
    enabled: !!formId && !USE_MOCKS,
  })
}

export function useFormActions() {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: KEY })
  return {
    save: useMutation({
      mutationFn: ({ formId, payload }: { formId?: string; payload: FormDraftPayload }) =>
        formId ? updateForm(formId, payload) : createForm(payload),
      onSuccess: refresh,
    }),
    publish: useMutation({ mutationFn: (formId: string) => publishForm(formId), onSuccess: refresh, onError: refresh }),
    remove: useMutation({ mutationFn: (formId: string) => deleteForm(formId), onSuccess: refresh }),
  }
}
