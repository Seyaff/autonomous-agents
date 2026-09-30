import axios from "axios"
import { toast } from "sonner"

const API = axios.create({
  baseURL:
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1",
  withCredentials: true,
  timeout: 30000,
})

API.interceptors.request.use(
  (config) => {
    const requestId = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    config.headers["X-Request-ID"] = requestId
    return config
  },
  (error) => Promise.reject(error)
)

API.interceptors.response.use(
  (response) => response,
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

    if (status === 401) {
      // Don't toast or redirect if we're already on /login or hitting auth endpoints
      if (currentPath !== "/login" && !isAuthEndpoint) {
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