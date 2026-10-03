"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  getLatestMenuUpload,
  getMenuUpload,
  uploadMenuPdf,
  type MenuJob,
} from "@/services/setup/setup.service"

const isActive = (job: MenuJob) => job.status === "queued" || job.status === "running"

/** A menu upload with real progress. The upload returns at once, the job runs on
 * the server, and this polls it every second while it's running. A reload picks
 * up the most recent job, so nothing is lost if the owner leaves the page. */
export function useMenuUpload(enabled: boolean) {
  const queryClient = useQueryClient()
  const [jobId, setJobId] = React.useState<string | null>(null)

  const latest = useQuery({
    queryKey: ["menu", "latest"],
    queryFn: getLatestMenuUpload,
    enabled,
    refetchOnWindowFocus: false,
  })

  const activeId = jobId ?? (latest.data && isActive(latest.data) ? latest.data.job_id : null)

  const job = useQuery({
    queryKey: ["menu", "job", activeId],
    queryFn: () => getMenuUpload(activeId as string),
    enabled: !!activeId,
    refetchInterval: (query) => {
      const data = query.state.data
      return data && isActive(data) ? 1000 : false
    },
    refetchOnWindowFocus: false,
  })

  const current: MenuJob | null = job.data ?? latest.data ?? null

  // When a reading finishes, the dish list and the latest job are out of date.
  const finishedStatus = job.data?.status
  React.useEffect(() => {
    if (finishedStatus === "done" || finishedStatus === "failed") {
      queryClient.invalidateQueries({ queryKey: ["tenant", "menu-items"] })
      queryClient.invalidateQueries({ queryKey: ["menu", "latest"] })
    }
  }, [finishedStatus, queryClient])

  const start = useMutation({
    mutationFn: (file: File) => uploadMenuPdf(file),
    onSuccess: (result) => {
      setJobId(result.job_id)
      queryClient.invalidateQueries({ queryKey: ["menu", "latest"] })
    },
  })

  /** Forget the failed job so the owner can upload again. */
  const reset = React.useCallback(() => {
    setJobId(null)
    queryClient.setQueryData(["menu", "latest"], null)
  }, [queryClient])

  return { current, start, reset, loading: latest.isLoading }
}

export { isActive }
