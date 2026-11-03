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
        { label: 'Why did the latest run fail?', prompt: 'Why did the most recent run fail? Explain it in plain words and say what it cost.' },
        { label: 'How many runs lost a payment?', prompt: 'How many runs ended with PayPal showing a capture that the app did not record? List them.' },
      ],
    }
  })
}
