import axios from "axios"
import { toast } from "sonner"

const getBaseURL = () => {
  // In production with rewrites, use relative path
  // In development, use the backend URL directly
  if (typeof window !== "undefined") {
    // Client-side: use relative path (proxied by Next.js rewrites)
    return "/api"
  }
  // Server-side: use actual backend URL
  return process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1"
}

const API = axios.create({
  baseURL: getBaseURL(),
  withCredentials: true,
  timeout: 30000,
})

API.interceptors.request.use(
  (config) => {
    const requestId = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    config.headers["X-Request-ID"] = requestId
    if (process.env.NODE_ENV === "development") {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`)
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Only one refresh runs at a time. Requests that fail meanwhile wait for it, then retry.
let refreshing: Promise<boolean> | null = null
const NO_REFRESH = /\/auth\/(login|signup|refresh|logout|logout-all|google)/
// Staff screens (the iPad and kitchen) have their own PIN session. An owner's refresh cookie
// can't renew it, and a 401 there means "sign in with your PIN", not "log in to the dashboard".
const STAFF_PATH = /^\/staff\//

function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    // A plain axios call, so this refresh never goes through the interceptors below.
    refreshing = axios
      .post("/api/auth/refresh", null, { withCredentials: true, timeout: 30000 })
      .then(() => true)
      .catch(() => false)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

API.interceptors.response.use(
  (response) => {
    if (process.env.NODE_ENV === "development") {
      console.log(`[API] Response ${response.status} from ${response.config.url}`)
    }
    return response
  },
  async (error) => {
    const requestId = error.config?.headers?.["X-Request-ID"] || "unknown"
    // A validation error from the server comes as a list of field problems. Show it as one readable sentence,
    // because React can't display a list of objects, and the page would crash.
    const rawDetail = error.response?.data?.detail
    if (Array.isArray(rawDetail) && error.response) {
      error.response.data.detail =
        rawDetail.map((d: { msg?: string }) => d?.msg).filter(Boolean).join(". ") || "Check the form and try again."
    }

    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "Request failed"

    const status = error.response?.status

    // An expired access token is renewed once from the refresh cookie, then the request is retried.
    const staffRequest = STAFF_PATH.test(error.config?.url ?? "")
    if (status === 401 && error.config && !error.config._retried && !NO_REFRESH.test(error.config.url ?? "") && !staffRequest) {
      if (await refreshSession()) {
        error.config._retried = true
        return API.request(error.config)
      }
    }

    const currentPath =
      typeof window !== "undefined" ? window.location.pathname : ""
    const isAuthEndpoint = error.config?.url?.includes("/auth/")

    if (process.env.NODE_ENV === "development") {
      console.error(`[API] Error ${status} on ${error.config?.url}:`, error.response?.data)
    }

    if (status === 401) {
      // A 401 on the session check just means "not signed in yet". Only a
      // signed-in user whose session ran out is sent back to login.
      const publicPage = ["/login", "/signup", "/privacy"].includes(currentPath)
      const sessionCheck = /\/(user|auth)\/me$/.test(error.config?.url ?? "")
      if (!publicPage && !isAuthEndpoint && !sessionCheck && !staffRequest) {
        toast.error("Session expired. Please log in again.")
        if (typeof window !== "undefined") {
          window.location.href = "/login"
        }
      }
      return Promise.reject(error)
    }

    if (status === 403) {
      if (!isAuthEndpoint) toast.error("Access denied")
      return Promise.reject(error)
    }

    if (status >= 500) {
      toast.error(`Server error (${requestId}). Please try again.`)
      return Promise.reject(error)
    }

    if (!isAuthEndpoint) toast.error(message)
    return Promise.reject(error)
  }
)

export default API