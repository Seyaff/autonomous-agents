"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { finishSetup, postSetupStep, type SetupAction } from "@/services/setup/setup.service"
import { SETUP_QUERY_KEY } from "@/hooks/setup/use-setup-state"

/** Saves one step's outcome on the server. The gate reads the result, so the
 * owner can't skip ahead by typing a URL. */
export function useSetupStep() {
  const queryClient = useQueryClient()

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: SETUP_QUERY_KEY })
  }

  const complete = useMutation({
    mutationFn: ({ step, action }: { step: string; action: SetupAction }) => postSetupStep(step, action),
    onSuccess: refresh,
  })

  const finish = useMutation({
    mutationFn: finishSetup,
    onSuccess: async () => {
      refresh()
      await queryClient.invalidateQueries({ queryKey: ["me"] })
    },
  })

  return { complete, finish }
}
