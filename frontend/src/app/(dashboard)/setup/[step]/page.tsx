import { notFound } from "next/navigation"
import { SetupStepContent } from "@/components/setup/steps/step-content"
import { isSetupRoute } from "@/lib/setup"

export default async function SetupStepPage({
  params,
}: {
  params: Promise<{ step: string }>
}) {
  const { step } = await params
  if (!isSetupRoute(step)) notFound()
  return <SetupStepContent step={step} />
}
