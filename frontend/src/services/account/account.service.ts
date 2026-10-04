import API from "@/lib/axios-client"

export interface DeviceSession {
  session_id: string
  user_agent: string
  created_at: string
  last_used_at: string
  current: boolean
}

export const listSessions = async (): Promise<DeviceSession[]> => {
  const res = await API.get("/auth/sessions")
  return res.data.sessions
}

export const signOutDevice = async (sessionId: string) => {
  const res = await API.delete(`/auth/sessions/${sessionId}`)
  return res.data
}

export const signOutEverywhere = async () => {
  const res = await API.post("/auth/logout-all")
  return res.data
}

export const changePassword = async (currentPassword: string, newPassword: string) => {
  const res = await API.post("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return res.data
}

export interface TwoFactorStatus {
  enabled: boolean
  recovery_codes_left: number
}

export const twoFactorStatus = async (): Promise<TwoFactorStatus> => (await API.get("/auth/2fa/status")).data

export const startTwoFactor = async (): Promise<{ secret: string; otpauth_uri: string }> =>
  (await API.post("/auth/2fa/setup")).data

export const enableTwoFactor = async (code: string): Promise<{ recovery_codes: string[] }> =>
  (await API.post("/auth/2fa/enable", { code })).data

export const disableTwoFactor = async (password: string, code: string) =>
  (await API.post("/auth/2fa/disable", { password, code })).data
