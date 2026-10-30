export function faultLabel(fault: string): string {
  // "F1_LOST_CAPTURE_RESPONSE" -> "F1 Lost capture response"
  const [code, ...rest] = fault.split('_')
  const words = rest.join(' ').toLowerCase()
  return `${code} ${words.charAt(0).toUpperCase()}${words.slice(1)}`
}

export function timeAgo(epochSeconds: number, now = Date.now()): string {
  const s = Math.max(0, Math.round(now / 1000 - epochSeconds))
  if (s < 5) return 'just now'
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

export const shortId = (runId: string): string => runId.replace(/^run_/, '')
