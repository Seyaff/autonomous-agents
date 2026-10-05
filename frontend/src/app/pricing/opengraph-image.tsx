import { ImageResponse } from "next/og"

import { siteUrl } from "@/lib/site"

export const alt = "Siyaf pricing"
export const size = { width: 1200, height: 630 }
export const contentType = "image/png"

export default function Image() {
  return new ImageResponse(
    (
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: "100%", height: "100%", padding: 72, background: "#0b0b0c", color: "#fafafa" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20, fontSize: 32 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`${siteUrl()}/brand/logo-light-1024.png`} width={56} height={56} alt="" />
          Siyaf
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 68, fontWeight: 700, lineHeight: 1.1 }}>Siyaf pricing</div>
          <div style={{ fontSize: 32, color: "#a1a1aa" }}>From Rs 2,999 a month. 3-day free trial.</div>
        </div>
      </div>
    ),
    size,
  )
}
