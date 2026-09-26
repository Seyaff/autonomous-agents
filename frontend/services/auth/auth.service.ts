import API from "@/lib/axios-client"

export const getUserQuery = async () => {
    const response = await API.get("/user/me")
    return response.data
}