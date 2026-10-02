export interface KpiValue {
  key: string
  label: string
  value: number
  format: "number" | "currency" | "percent"
}

export const MOCK_KPIS: KpiValue[] = [
  { key: "conversations", label: "Conversations", value: 18, format: "number" },
  { key: "orders", label: "Orders", value: 4, format: "number" },
  { key: "revenue", label: "Revenue", value: 6800, format: "currency" },
  { key: "needs_you", label: "Needs you", value: 1, format: "number" },
]
