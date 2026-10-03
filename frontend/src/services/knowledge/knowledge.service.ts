import API from "@/lib/axios-client"

export type KnowledgeCategory = "deal" | "policy" | "recipe" | "faq"

export interface KnowledgeDocument {
  doc_id: string
  title: string
  category?: KnowledgeCategory | string
  doc_type: "pdf" | "text"
  chunks_count: number
  content_snippet?: string
  created_at: string
}

export interface KnowledgeList {
  total: number
  documents: KnowledgeDocument[]
}

export const listKnowledge = async (): Promise<KnowledgeList> => {
  const res = await API.get("/tenant/knowledge")
  return res.data
}

export const addTextKnowledge = async (payload: {
  title: string
  content: string
  category: KnowledgeCategory
}) => {
  const res = await API.post("/tenant/knowledge/add-text", payload)
  return res.data
}

export const uploadPdfKnowledge = async (file: File) => {
  const form = new FormData()
  form.append("file", file)
  const res = await API.post("/tenant/knowledge/upload-pdf", form)
  return res.data
}

export const deleteKnowledge = async (docId: string) => {
  const res = await API.delete(`/tenant/knowledge/${docId}`)
  return res.data
}

export interface KnowledgeSearchResult {
  status: string
  query: string
  retrieved_context: string
}

export const testKnowledgeSearch = async (query: string): Promise<KnowledgeSearchResult> => {
  const res = await API.post("/tenant/knowledge/test-search", { query })
  return res.data
}
