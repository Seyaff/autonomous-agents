/** Flips every data hook between mock data and the real API. Set in
 * .env.local / .env.example as NEXT_PUBLIC_USE_MOCKS. */
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true"
