"use client"

import { useQuery } from "@tanstack/react-query"
import { getUserQuery } from "../../../services/auth/auth.service"

export const useGetCurrentUser = () => {
    return useQuery({
        queryKey: ["me"],
        queryFn: getUserQuery
    })
}