import { createAiHarness, directLlmRunner } from 'ag-studio'
import type { AgAiHarness, AgAiTool, AgLlmAdapter, AgStudioApi } from 'ag-studio'
import type { Run } from '../types'
import { AGENT_ADDENDUM, describeRun, findRun, listRuns } from './runFacts'

/**
 * Studio's own agents (lead, data, page, planning, widget) plus two tools that read the stored runs.
 * The lead agent gets the tools and a short brief, so "why did run X fail?" is answered from the
 * stored Result, while building charts and tables still works as before.
 */
export function buildHarness(api: AgStudioApi, adapter: AgLlmAdapter, getRuns: () => Run[]): AgAiHarness {
  const explainRun: AgAiTool = api.defineAiTool({
    name: 'explain_run',
    description: 'Get the recorded facts for one DriftGuard run: what was injected, what PayPal recorded, what the app recorded, the verdict and the money impact. Use it to answer why a run failed.',
    params: (s) => s.object({ run_id: s.string({ description: 'The run id, full or the short form shown in the table' }) }),
    execute: ({ run_id }, ctx) => {
      const run = findRun(getRuns(), run_id)
      return run ? ctx.success(describeRun(run)) : ctx.error(`No run matches "${run_id}". Call list_runs to see the ids.`)
    },
  })
  const listRunsTool: AgAiTool = api.defineAiTool({
    name: 'list_runs',
    description: 'List every stored DriftGuard run with its short id, fault, verdict and money impact, newest first.',
    params: (s) => s.object({}),
    execute: (_args, ctx) => ctx.success(listRuns(getRuns())),
  })

  return createAiHarness(api, ({ builtIn }) => {
    const lead = {
      ...builtIn.lead,
      instructions: (ctx: Parameters<NonNullable<typeof builtIn.lead.instructions>>[0], params: undefined) =>
        [builtIn.lead.instructions?.(ctx, params), AGENT_ADDENDUM].filter(Boolean).join('\n\n'),
      tools: (ctx: Parameters<NonNullable<typeof builtIn.lead.tools>>[0], params: undefined) => [
        ...(builtIn.lead.tools?.(ctx, params) ?? []),
        explainRun,
        listRunsTool,
      ],
    }
    return {
      agents: [
        directLlmRunner({ ...lead, adapter }),
        directLlmRunner({ ...builtIn.data, adapter }),
        directLlmRunner({ ...builtIn.page, adapter }),
        directLlmRunner({ ...builtIn.planning, adapter }),
        directLlmRunner({ ...builtIn.widget, adapter }),
      ],
      primary: 'lead',
      promptStarters: [
        { label: 'What does this run do?', prompt: 'Explain what the latest run tests, what happened, and its verdict in plain words.' },
        { label: 'Summarize this error', prompt: 'Summarize the most recent run error or failure and cite the recorded evidence.' },
        { label: 'How would I fix it?', prompt: 'For the latest failed run, explain a safe fix based on its evidence. Do not claim code was changed.' },
      ],
    }
  })
}
