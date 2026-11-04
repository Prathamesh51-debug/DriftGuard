export const RUNS_POLL_INTERVAL_MS = 2_000
export const MAX_RUNS_POLL_DELAY_MS = 30_000

export function nextPollDelay(consecutiveFailures: number): number {
  if (!Number.isFinite(consecutiveFailures) || consecutiveFailures <= 1) return RUNS_POLL_INTERVAL_MS
  const failureCount = Math.floor(consecutiveFailures)
  return Math.min(RUNS_POLL_INTERVAL_MS * 2 ** (failureCount - 1), MAX_RUNS_POLL_DELAY_MS)
}
