import { describe, expect, it } from 'vitest'
import type { AgAiConversationItem, AgLlmRequest } from 'ag-studio'
import { createAnthropicAdapter, toAnthropicBody, toAnthropicMessages, toAgResponse } from './anthropicAdapter'

const userMsg = (text: string): AgAiConversationItem => ({
  id: 'u', kind: 'input', type: 'message', role: 'user', status: 'completed', content: [{ type: 'text', text }],
})
const call = (id: string, name: string, args: string): AgAiConversationItem => ({
  id, kind: 'output', type: 'function_call', callId: id, name, arguments: args, status: 'completed',
})
const callOut = (id: string, output: string): AgAiConversationItem => ({
  type: 'function_call_output', callId: id, output, status: 'completed',
})

const request = (input: AgLlmRequest['input'], extra: Partial<AgLlmRequest> = {}): AgLlmRequest => ({
  input, responseFormat: { type: 'text' }, ...extra,
})

describe('toAnthropicMessages', () => {
  it('maps a tool round trip and merges same-role neighbours', () => {
    const { messages } = toAnthropicMessages([
      userMsg('why did run 1 fail?'),
      call('c1', 'explain_run', '{"run_id":"r1"}'),
      call('c2', 'list_runs', '{}'),
      callOut('c1', 'facts one'),
      callOut('c2', 'facts two'),
    ])
    expect(messages).toEqual([
      { role: 'user', content: [{ type: 'text', text: 'why did run 1 fail?' }] },
      { role: 'assistant', content: [
        { type: 'tool_use', id: 'c1', name: 'explain_run', input: { run_id: 'r1' } },
        { type: 'tool_use', id: 'c2', name: 'list_runs', input: {} },
      ] },
      { role: 'user', content: [
        { type: 'tool_result', tool_use_id: 'c1', content: 'facts one' },
        { type: 'tool_result', tool_use_id: 'c2', content: 'facts two' },
      ] },
    ])
  })

  it('survives malformed tool arguments', () => {
    const { messages } = toAnthropicMessages([call('c1', 'x', 'not json')])
    expect(messages[0].content[0]).toMatchObject({ type: 'tool_use', input: {} })
  })

  it('moves system messages into the system prompt', () => {
    const sys: AgAiConversationItem = { id: 's', kind: 'input', type: 'message', role: 'system', status: 'completed', content: [{ type: 'text', text: 'be brief' }] }
    const { system, messages } = toAnthropicMessages([sys, userMsg('hi')])
    expect(system).toEqual(['be brief'])
    expect(messages).toHaveLength(1)
  })
})

describe('toAnthropicBody', () => {
  it('sends instructions, client tools and the forced tool, and drops non-client tools', () => {
    const body = toAnthropicBody(request([userMsg('hi')], {
      instructions: 'You explain DriftGuard runs.',
      tools: [
        { name: 'explain_run', description: 'd', parameters: { properties: { run_id: { type: 'string' } } } },
        { name: 'web', description: 'd', parameters: {}, kind: 'server' },
      ],
      toolChoice: { name: 'explain_run' },
    }))
    expect(body.system).toBe('You explain DriftGuard runs.')
    expect(body.tools).toEqual([{ name: 'explain_run', description: 'd', input_schema: { type: 'object', properties: { run_id: { type: 'string' } } } }])
    expect(body.tool_choice).toEqual({ type: 'tool', name: 'explain_run' })
  })

  it('asks for JSON when the response format is json', () => {
    const body = toAnthropicBody(request([userMsg('hi')], { responseFormat: { type: 'json', name: 'x', schema: { type: 'object' } } }))
    expect(body.system).toContain('JSON Schema')
  })
})

describe('toAgResponse', () => {
  it('turns text and tool_use blocks into output items with string arguments', () => {
    const res = toAgResponse({
      id: 'm1', stop_reason: 'tool_use', usage: { input_tokens: 10, output_tokens: 5 },
      content: [{ type: 'text', text: 'Let me check.' }, { type: 'tool_use', id: 't1', name: 'explain_run', input: { run_id: 'r1' } }],
    })
    expect(res.status).toBe('completed')
    expect(res.usage).toEqual({ inputTokens: 10, outputTokens: 5 })
    expect(res.output.map((o) => o.type)).toEqual(['message', 'function_call'])
    expect(res.output[1]).toMatchObject({ callId: 't1', name: 'explain_run', arguments: '{"run_id":"r1"}' })
  })

  it('marks a reply cut off by the token limit as incomplete', () => {
    const res = toAgResponse({ id: 'm', stop_reason: 'max_tokens', content: [{ type: 'text', text: 'partial' }] })
    expect(res.status).toBe('incomplete')
    expect(res.incompleteDetails).toEqual({ reason: 'max_output_tokens' })
  })
})

describe('createAnthropicAdapter', () => {
  const fakeFetch = (status: number, body: unknown) => (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch

  it('streams the text and resolves with the response', async () => {
    const adapter = createAnthropicAdapter('http://ai', fakeFetch(200, { id: 'm', stop_reason: 'end_turn', content: [{ type: 'text', text: 'Hello' }] }))
    const turn = adapter.executeTurn(request([userMsg('hi')]))
    const events = []
    for await (const e of turn.stream) events.push(e)
    expect(events).toEqual([{ type: 'TEXT_MESSAGE_CHUNK', messageId: 'm-text', role: 'assistant', delta: 'Hello' }])
    expect((await turn.complete).status).toBe('completed')
  })

  it('reports the service message when it refuses (spend limit)', async () => {
    const adapter = createAnthropicAdapter('http://ai', fakeFetch(429, { detail: 'Spend limit $1.50 reached' }))
    const res = await adapter.executeTurn(request([userMsg('hi')])).complete
    expect(res.status).toBe('failed')
    expect(res.error?.message).toBe('Spend limit $1.50 reached')
  })

  it('says the service is unreachable instead of throwing', async () => {
    const down = (async () => { throw new TypeError('fetch failed') }) as unknown as typeof fetch
    const turn = createAnthropicAdapter('http://ai', down).executeTurn(request([userMsg('hi')]))
    const events = []
    for await (const e of turn.stream) events.push(e)
    expect(events).toEqual([])
    const res = await turn.complete
    expect(res.status).toBe('failed')
    expect(res.error?.message).toContain('Could not reach the AI service')
  })
})
