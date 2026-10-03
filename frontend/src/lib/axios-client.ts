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

API.interceptors.response.use(
  (response) => {
    if (process.env.NODE_ENV === "development") {
      console.log(`[API] Response ${response.status} from ${response.config.url}`)
    }
    return response
  },
  (error) => {
    const requestId = error.config?.headers?.["X-Request-ID"] || "unknown"
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "Request failed"

    const status = error.response?.status
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
      if (!publicPage && !isAuthEndpoint && !sessionCheck) {
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