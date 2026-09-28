"use client"

import { useMutation } from "@tanstack/react-query"
import { queryAgentMutationFn } from "../../../services/agent/agent.service"


export const useQueryAgent = () => {
    return useMutation({
        mutationKey: ["agent-query"],
        mutationFn: queryAgentMutationFn,
    })
}