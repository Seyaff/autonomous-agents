// The setup steps, in order. The backend has the same list (SETUP_STEPS in
// app/core/setup_state.py). Keep the two in sync.

export const SETUP_STEPS = ["restaurant", "menu", "hours", "agent", "test", "whatsapp"] as const
export type SetupStep = (typeof SETUP_STEPS)[number]

/** Every URL under /setup, in the order a new owner passes through them. */
export const SETUP_ROUTE_ORDER = ["welcome", ...SETUP_STEPS, "done"] as const
export type SetupRoute = (typeof SETUP_ROUTE_ORDER)[number]

export const SKIPPABLE: ReadonlySet<SetupStep> = new Set<SetupStep>(["menu", "whatsapp"])

/** Steps 1–6 show "Step N of 6" and a progress bar. Welcome and done don't. */
export const NUMBERED_STEPS = SETUP_STEPS.length

export function isSetupRoute(value: string): value is SetupRoute {
  return (SETUP_ROUTE_ORDER as readonly string[]).includes(value)
}

export function isSetupStep(value: string): value is SetupStep {
  return (SETUP_STEPS as readonly string[]).includes(value)
}

export function routeIndex(route: string): number {
  return (SETUP_ROUTE_ORDER as readonly string[]).indexOf(route)
}

/** 1-based position for "Step N of 6". Null for welcome and done. */
export function stepNumber(step: SetupRoute): number | null {
  const index = (SETUP_STEPS as readonly string[]).indexOf(step)
  return index === -1 ? null : index + 1
}

export function isRequired(step: SetupStep): boolean {
  return !SKIPPABLE.has(step)
}

export function nextRoute(current: SetupRoute): SetupRoute {
  const index = routeIndex(current)
  return SETUP_ROUTE_ORDER[Math.min(index + 1, SETUP_ROUTE_ORDER.length - 1)]
}
