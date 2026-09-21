import axios from "axios"

const API = axios.create({
  baseURL:
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1",
  withCredentials: true,
  timeout: 10000,
});



export default API