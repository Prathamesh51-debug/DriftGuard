import type {
  AgAiConversationItem,
  AgAiEvent,
  AgAiOutputItem,
  AgAiToolSchema,
  AgLlmRequest,
  AgLlmResponse,
} from 'ag-studio'

/**
 * Studio's LLM adapter. It turns Studio's request into an Anthropic Messages body, sends it to
 * DriftGuard's AI service (which holds the key, picks the model and enforces the spend limit),
 * and turns the reply back into what Studio's agent loop reads. No key ever reaches the browser.
 */

export interface AnthropicBlock {
  type: string
  [key: string]: unknown
}
export interface AnthropicMessage {
  role: 'user' | 'assistant'
  content: AnthropicBlock[]
}
export interface AnthropicTool {
  name: string
  description: string
  input_schema: Record<string, unknown>
}
export interface AnthropicBody {
  system?: string
  messages: AnthropicMessage[]
  tools?: AnthropicTool[]
  tool_choice?: { type: 'auto' | 'any' | 'none' } | { type: 'tool'; name: string }
  max_tokens: number
}
export interface AnthropicReply {
  id: string
  model?: string
  stop_reason: string | null
  content: AnthropicBlock[]
  usage?: { input_tokens: number; output_tokens: number }
}

const MAX_TOKENS = 1024

function parseArgs(raw: string): Record<string, unknown> {
  try {
    const value: unknown = JSON.parse(raw || '{}')
    return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

/** Append a block, merging into the previous message when it has the same role (the API wants strict alternation). */
function push(messages: AnthropicMessage[], role: AnthropicMessage['role'], block: AnthropicBlock): void {
  const last = messages[messages.length - 1]
  if (last && last.role === role) last.content.push(block)
  else messages.push({ role, content: [block] })
}

export function toAnthropicMessages(input: AgAiConversationItem[]): { system: string[]; messages: AnthropicMessage[] } {
  const system: string[] = []
  const messages: AnthropicMessage[] = []
  for (const item of input) {
    if (item.type === 'message' && item.kind === 'input') {
      const text = item.content.flatMap((c) => (c.type === 'text' ? [c.text] : [])).join('\n')
      if (!text) continue
      if (item.role === 'system') system.push(text)
      else push(messages, 'user', { type: 'text', text })
    } else if (item.type === 'message') {
      const text = item.content.map((c) => (c.type === 'text' ? c.text : c.refusal)).join('\n')
      if (text) push(messages, 'assistant', { type: 'text', text })
    } else if (item.type === 'function_call') {
      push(messages, 'assistant', { type: 'tool_use', id: item.callId, name: item.name, input: parseArgs(item.arguments) })
    } else if (item.type === 'function_call_output') {
      push(messages, 'user', { type: 'tool_result', tool_use_id: item.callId, content: item.output })
    }
    // reasoning items are not sent back
  }
  return { system, messages }
}

export function toAnthropicTools(tools: AgAiToolSchema[] | undefined): AnthropicTool[] {
  return (tools ?? [])
    .filter((t) => t.kind === undefined || t.kind === 'client')
    .map((t) => ({
      name: t.name,
      description: t.description,
      input_schema: { type: 'object', ...(t.parameters as Record<string, unknown>) },
    }))
}

export function toAnthropicBody(req: AgLlmRequest): AnthropicBody {
  const { system, messages } = toAnthropicMessages(req.input)
  const instructions = [req.instructions, ...system]
  if (req.responseFormat.type === 'json') {
    instructions.push(`Reply with only a JSON value that matches this JSON Schema, with no other text:\n${JSON.stringify(req.responseFormat.schema)}`)
  }
  const tools = toAnthropicTools(req.tools)
  const body: AnthropicBody = { messages, max_tokens: MAX_TOKENS }
  const joined = instructions.filter(Boolean).join('\n\n')
  if (joined) body.system = joined
  if (tools.length > 0) {
    body.tools = tools
    const choice = req.toolChoice
    if (choice === 'none') body.tool_choice = { type: 'none' }
    else if (choice === 'required') body.tool_choice = { type: 'any' }
    else if (choice && typeof choice === 'object') body.tool_choice = { type: 'tool', name: choice.name }
  }
  return body
}

function outputItems(reply: AnthropicReply): AgAiOutputItem[] {
  const items: AgAiOutputItem[] = []
  const text = reply.content.flatMap((b) => (b.type === 'text' && typeof b.text === 'string' ? [b.text] : [])).join('')
  if (text) {
    items.push({
      id: `${reply.id}-text`,
      kind: 'output',
      type: 'message',
      role: 'assistant',
      status: 'completed',
      content: [{ type: 'text', text, annotations: [] }],
    })
  }
  for (const b of reply.content) {
    if (b.type === 'tool_use' && typeof b.id === 'string' && typeof b.name === 'string') {
      items.push({
        id: b.id,
        kind: 'output',
        type: 'function_call',
        callId: b.id,
        name: b.name,
        arguments: JSON.stringify(b.input ?? {}),
        status: 'completed',
      })
    }
  }
  return items
}

export function toAgResponse(reply: AnthropicReply): AgLlmResponse {
  const cut = reply.stop_reason === 'max_tokens'
  return {
    id: reply.id,
    createdAt: Date.now(),
    status: cut ? 'incomplete' : 'completed',
    incompleteDetails: cut ? { reason: 'max_output_tokens' } : undefined,
    output: outputItems(reply),
    model: reply.model,
    usage: reply.usage ? { inputTokens: reply.usage.input_tokens, outputTokens: reply.usage.output_tokens } : undefined,
  }
}

export function toAgEvents(response: AgLlmResponse): AgAiEvent[] {
  const events: AgAiEvent[] = []
  for (const item of response.output) {
    if (item.type === 'message') {
      const text = item.content.map((c) => (c.type === 'text' ? c.text : c.refusal)).join('')
      events.push({ type: 'TEXT_MESSAGE_CHUNK', messageId: item.id, role: 'assistant', delta: text })
    } else if (item.type === 'function_call') {
      events.push({ type: 'TOOL_CALL_CHUNK', toolCallId: item.callId, toolCallName: item.name, delta: item.arguments })
    }
  }
  return events
}

function failed(message: string, code: string): AgLlmResponse {
  return { id: `error-${Date.now()}`, createdAt: Date.now(), status: 'failed', output: [], error: { code, message } }
}

async function errorMessage(resp: Response): Promise<string> {
  try {
    const body = (await resp.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    /* fall through */
  }
  return `The AI service answered HTTP ${resp.status}`
}

export function createAnthropicAdapter(baseUrl: string, fetchImpl: typeof fetch = fetch) {
  return {
    executeTurn(request: AgLlmRequest, options?: { signal?: AbortSignal }) {
      const complete: Promise<AgLlmResponse> = (async () => {
        try {
          const resp = await fetchImpl(`${baseUrl}/llm/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toAnthropicBody(request)),
            signal: options?.signal,
          })
          if (!resp.ok) return failed(await errorMessage(resp), `http_${resp.status}`)
          return toAgResponse((await resp.json()) as AnthropicReply)
        } catch (err) {
          if (options?.signal?.aborted) return { ...failed('The request was cancelled.', 'cancelled'), status: 'cancelled' as const }
          return failed(`Could not reach the AI service at ${baseUrl}. Is it running?`, err instanceof Error ? err.name : 'network')
        }
      })()
      async function* stream(): AsyncGenerator<AgAiEvent> {
        const response = await complete
        for (const event of toAgEvents(response)) yield event
      }
      return { stream: stream(), complete }
    },
  }
}
