import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

// Create configured Axios instance
export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "/api/v1",
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
  timeout: 15000,
});

// Request Interceptor
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Attach auth token if present in browser localStorage
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("auth_token");
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      const activeTenant = localStorage.getItem("active_tenant_id");
      if (activeTenant && config.headers && !config.headers["X-Tenant-Id"]) {
        config.headers["X-Tenant-Id"] = activeTenant;
      }
    }

    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response Interceptor
apiClient.interceptors.response.use(
  (response) => {
    // Return data directly for clean consumption
    return response.data;
  },
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    // Extract FastAPI detailed error messages
    const status = error.response?.status;
    const detail =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "An unexpected server error occurred";

    if (status === 401) {
      // Clear token on unauthorized if in browser
      if (typeof window !== "undefined") {
        console.warn("[Auth] Session expired or unauthorized.");
      }
    }

    const enhancedError = new Error(detail);
    (enhancedError as any).status = status;
    (enhancedError as any).originalError = error;

    return Promise.reject(enhancedError);
  }
);

export default apiClient;
