"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  addTextKnowledge,
  deleteKnowledge,
  listKnowledge,
  testKnowledgeSearch,
  uploadPdfKnowledge,
  type KnowledgeCategory,
} from "@/services/knowledge/knowledge.service"
import { USE_MOCKS } from "@/lib/mocks"

const KEY = ["tenant", "knowledge"] as const

export function useKnowledge() {
  const queryClient = useQueryClient()
  const list = useQuery({
    queryKey: KEY,
    queryFn: listKnowledge,
    enabled: !USE_MOCKS,
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: KEY })

  const addText = useMutation({
    mutationFn: (payload: { title: string; content: string; category: KnowledgeCategory }) =>
      addTextKnowledge(payload),
    onSuccess: refresh,
  })

  const uploadPdf = useMutation({
    mutationFn: (file: File) => uploadPdfKnowledge(file),
    onSuccess: refresh,
  })

  const remove = useMutation({
    mutationFn: (docId: string) => deleteKnowledge(docId),
    onSuccess: refresh,
  })

  const search = useMutation({
    mutationFn: (query: string) => testKnowledgeSearch(query),
  })

  return { list, addText, uploadPdf, remove, search }
}
