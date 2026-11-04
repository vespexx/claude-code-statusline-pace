import type { Kind } from '../types'
import { expect, test } from 'claude-code/testing'
import {
  bandRows,
  fmt,
  mergeState,
  oauthPlans,
  exhausted,
  offPace,
  oneWin,
  planOf,
  readOauth,
  resetOauthCache,
  agentsRow,
  lastModel,
  readAgents,
  setAgentsDir,
  shortLabel,
  stateWins,
  winsOf,
} from '../hooks/register'
import cases from './layout-cases'

// --- fmt tests ---

test('fmt 5h returns HH:MM', () => {
  const ms = new Date(2027, 0, 15, 14, 30).getTime()
  expect(fmt('5h', ms)).toBe('14:30')
})

test('fmt 1d returns HH:MM', () => {
  const ms = new Date(2027, 0, 15, 14, 30).getTime()
  expect(fmt('1d', ms)).toBe('14:30')
})

test('fmt 7d returns Ddd-HH:MM', () => {
  // 2027-01-15 is a Friday
  const ms = new Date(2027, 0, 15, 8, 52).getTime()
  expect(fmt('7d', ms)).toBe('Fri-08:52')
})

test('fmt 1mo returns DD.MM (1-indexed month)', () => {
  const ms = new Date(2027, 0, 15).getTime() // Jan 15 2027
  expect(fmt('1mo', ms)).toBe('15.01')
})

// --- winsOf tests ---

test('winsOf drops unknown kinds and non-parsing resetsAt', () => {
  const rows = [
    { kind: 'five_hour', percentUsed: 60, resetsAt: new Date(Date.now() + 3600_000).toISOString() },
    { kind: 'seven_day', percentUsed: 40, resetsAt: new Date(Date.now() + 86400_000).toISOString() },
    { kind: 'unknown_kind', percentUsed: 10, resetsAt: new Date().toISOString() },
    { kind: 'five_hour', percentUsed: 20, resetsAt: 'not-a-date' },
  ]
  const wins = winsOf(rows)
  expect(wins.length).toBe(2)
  expect(wins[0]!.kind).toBe('5h')
  expect(wins[1]!.kind).toBe('7d')
})

// --- planOf tests ---

test('planOf opencode-go id returns go', () => {
  expect(planOf('glm-5.3-flash-cloud-opencode-go-direct')).toBe('go')
})

test('planOf string containing opencode-go returns go', () => {
  expect(planOf('some-opencode-go-model')).toBe('go')
})

test('planOf Go/Go Plus in label returns go', () => {
  expect(planOf('GLM (Go Plus, z.ai)')).toBe('go')
  expect(planOf('Model (Go, subscription)')).toBe('go')
})

test('planOf fable in id returns fable', () => {
  expect(planOf('fable-model-v1')).toBe('fable')
})

test('planOf fable in label item returns fable', () => {
  expect(planOf('Model (Fable, Cloud)')).toBe('fable')
})

test('planOf fable checked before claude', () => {
  expect(planOf('claude-fable-model (Fable)')).toBe('fable')
})

test('planOf openrouter in id returns openrouter', () => {
  expect(planOf('openrouter-model-v1')).toBe('openrouter')
})

test('planOf openrouter in label item returns openrouter', () => {
  expect(planOf('Model (OpenRouter, free)')).toBe('openrouter')
})

test('planOf openrouter checked before claude', () => {
  expect(planOf('claude-openrouter-model (OpenRouter)')).toBe('openrouter')
})

test('planOf zai in id returns zai', () => {
  expect(planOf('glm-5.3-flash-cloud-zai-direct')).toBe('zai')
})

test('planOf z.ai in label item returns zai', () => {
  expect(planOf('GLM (z.ai Lite $18)')).toBe('zai')
})

test('planOf Go Plus with z.ai still returns go (Go checked first)', () => {
  expect(planOf('GLM (Go Plus, z.ai)')).toBe('go')
})

test('planOf claude/opus/sonnet/haiku returns claude', () => {
  expect(planOf('claude-opus-5-5')).toBe('claude')
  expect(planOf('claude-sonnet-4')).toBe('claude')
  expect(planOf('claude-haiku-3')).toBe('claude')
  expect(planOf('opus-5')).toBe('claude')
})

test('planOf subscription in label returns claude', () => {
  // subscription without z.ai -> claude
  expect(planOf('Model (subscription)')).toBe('claude')
})

test('planOf unknown model returns empty', () => {
  expect(planOf('gpt-4')).toBe('')
  expect(planOf('')).toBe('')
})

// --- shortLabel tests ---

test('shortLabel keeps name and plan/estimate items', () => {
  const label = 'GLM5.3flash (Cloud, Go Plus, $ BEST, ≈360M вых.ток/мес, limit $180 = ×4.5 к $40, для проверки)'
  expect(shortLabel(label)).toBe('GLM5.3flash (Go Plus, ≈360M вых.ток/мес)')
})

test('shortLabel keeps z.ai and ≈ items, drops others like "пик …"', () => {
  const label = 'GLM5.3flash (Cloud, z.ai Lite $18, ★ …, ≈146–293M ток/нед при кэше 95%, пик …)'
  expect(shortLabel(label)).toBe('GLM5.3flash (z.ai Lite $18, ≈146–293M ток/нед при кэше 95%)')
})

test('shortLabel keeps Fable and OpenRouter tags', () => {
  const label = 'Model (Fable, OpenRouter, Cloud, ≈100M)'
  expect(shortLabel(label)).toBe('Model (Fable, OpenRouter, ≈100M)')
})

test('shortLabel no parentheses returns as-is', () => {
  expect(shortLabel('Opus 5.5')).toBe('Opus 5.5')
})

test('shortLabel drops non-plan items', () => {
  const label = 'Model (Cloud, Premium, $10, ≈100M ток/мес)'
  expect(shortLabel(label)).toBe('Model (≈100M ток/мес)')
})

// --- offPace truth table (matches statusline.py) ---

test('offPace 5h: (0.6, 0.4) false — on pace', () => {
  expect(offPace('5h', 0.6, 0.4)).toBe(false)
})

test('offPace 5h: (0.65, 0.4) true — 1.5x elapsed', () => {
  expect(offPace('5h', 0.65, 0.4)).toBe(true)
})

test('offPace 5h: (0.8, 0.1) true — 75% cap', () => {
  expect(offPace('5h', 0.8, 0.1)).toBe(true)
})

test('offPace 5h: (0.05, 0.6) false — well under', () => {
  expect(offPace('5h', 0.05, 0.6)).toBe(false)
})

test('offPace 1d: (0.48, 0.42) true — leads by >5pp (long window rule)', () => {
  expect(offPace('1d', 0.48, 0.42)).toBe(true)
})

test('offPace 1d: (0.45, 0.42) false — within 5pp', () => {
  expect(offPace('1d', 0.45, 0.42)).toBe(false)
})

test('offPace 1d: (0.92, 0.95) true — hard cap 90%', () => {
  expect(offPace('1d', 0.92, 0.95)).toBe(true)
})

test('offPace 7d: (0.48, 0.42) true — leads by >5pp', () => {
  expect(offPace('7d', 0.48, 0.42)).toBe(true)
})

test('offPace 7d: (0.45, 0.42) false — within 5pp', () => {
  expect(offPace('7d', 0.45, 0.42)).toBe(false)
})

test('offPace 7d: (0.92, 0.95) true — hard cap 90%', () => {
  expect(offPace('7d', 0.92, 0.95)).toBe(true)
})

test('offPace 7d: (0.88, 0.95) false — under 90% cap', () => {
  expect(offPace('7d', 0.88, 0.95)).toBe(false)
})

test('offPace 1mo: (0.73, 0.13) true — leads by >5pp', () => {
  expect(offPace('1mo', 0.73, 0.13)).toBe(true)
})

test('offPace 1mo: (0.91, 0.5) true — hard cap 90%', () => {
  expect(offPace('1mo', 0.91, 0.5)).toBe(true)
})

test('offPace 1mo: (0.89, 0.5) true — leads by >5pp (still off-pace below 90%)', () => {
  expect(offPace('1mo', 0.89, 0.5)).toBe(true)
})

test('offPace 1mo: (0.54, 0.5) false — under 90% and within 5pp', () => {
  expect(offPace('1mo', 0.54, 0.5)).toBe(false)
})

// --- stateWins tests ---

const NOW = Date.now()

test('stateWins go extracts 5h/1d/7d/1mo in order', () => {
  const state = {
    plans: {
      go: {
        '5h': { utilization: 0.14, reset: Math.floor(NOW / 1000) + 3 * 3600 },
        '1d': { utilization: 0.3, reset: Math.floor(NOW / 1000) + 86400 },
        '7d': { utilization: 0.45, reset: Math.floor(NOW / 1000) + 5 * 86400 },
        '1mo': { utilization: 0.73, reset: Math.floor(NOW / 1000) + 26 * 86400 },
      },
    },
  }
  const wins = stateWins(state, 'go')
  expect(wins.length).toBe(4)
  expect(wins[0]).toEqual({ kind: '5h', used: 0.14, resetsAt: expect.any(Number) })
  expect(wins[1]).toEqual({ kind: '1d', used: 0.3, resetsAt: expect.any(Number) })
  expect(wins[2]).toEqual({ kind: '7d', used: 0.45, resetsAt: expect.any(Number) })
  expect(wins[3]).toEqual({ kind: '1mo', used: 0.73, resetsAt: expect.any(Number) })
})

test('stateWins fable extracts 7d in order', () => {
  const state = {
    plans: {
      fable: {
        '7d': { utilization: 0.5, reset: Math.floor(NOW / 1000) + 4 * 86400 },
      },
    },
  }
  const wins = stateWins(state, 'fable')
  expect(wins.length).toBe(1)
  expect(wins[0]!.kind).toBe('7d')
})

test('stateWins openrouter extracts 1d/7d in order', () => {
  const state = {
    plans: {
      openrouter: {
        '1d': { utilization: 0.2, reset: Math.floor(NOW / 1000) + 86400 },
        '7d': { utilization: 0.5, reset: Math.floor(NOW / 1000) + 4 * 86400 },
      },
    },
  }
  const wins = stateWins(state, 'openrouter')
  expect(wins.length).toBe(2)
  expect(wins[0]!.kind).toBe('1d')
  expect(wins[1]!.kind).toBe('7d')
})

test('stateWins zai extracts 5h/7d in order', () => {
  const state = {
    plans: {
      zai: {
        '5h': { utilization: 0.2, reset: Math.floor(NOW / 1000) + 2 * 3600 },
        '7d': { utilization: 0.5, reset: Math.floor(NOW / 1000) + 4 * 86400 },
      },
    },
  }
  const wins = stateWins(state, 'zai')
  expect(wins.length).toBe(2)
  expect(wins[0]!.kind).toBe('5h')
  expect(wins[1]!.kind).toBe('7d')
})

test('stateWins claude falls back to subscription', () => {
  const state = {
    subscription: {
      '5h': { utilization: 0.6, reset: Math.floor(NOW / 1000) + 2 * 3600 },
      '7d': { utilization: 0.4, reset: Math.floor(NOW / 1000) + 4 * 86400 },
    },
  }
  const wins = stateWins(state, 'claude')
  expect(wins.length).toBe(2)
  expect(wins[0]!.kind).toBe('5h')
  expect(wins[1]!.kind).toBe('7d')
})

test('stateWins claude: empty plans.claude falls back to subscription', () => {
  const state = {
    plans: { claude: {} },
    subscription: { '5h': { utilization: 0.2, reset: Math.floor(NOW / 1000) + 60 } },
  }
  expect(stateWins(state, 'claude').length).toBe(1)
})

test('stateWins stale file (updated > 6h ago) returns empty', () => {
  const staleTime = Math.floor((NOW - 7 * 3600_000) / 1000) // 7 hours ago
  const state = {
    updated: staleTime,
    plans: {
      go: {
        '5h': { utilization: 0.14, reset: Math.floor(NOW / 1000) + 3 * 3600 },
      },
    },
  }
  expect(stateWins(state, 'go')).toEqual([])
})

test('stateWins no updated key uses data (old router shape)', () => {
  const state = {
    subscription: {
      '5h': { utilization: 0.6, reset: Math.floor(NOW / 1000) + 2 * 3600 },
    },
  }
  const wins = stateWins(state, 'claude')
  expect(wins.length).toBe(1)
  expect(wins[0]!.kind).toBe('5h')
})

test('stateWins unknown shape returns empty', () => {
  expect(stateWins(null, 'go')).toEqual([])
  expect(stateWins({}, 'go')).toEqual([])
  expect(stateWins({ plans: {} }, 'go')).toEqual([])
  expect(stateWins({ plans: { go: 'not-an-object' } }, 'go')).toEqual([])
})

// --- oneWin tests ---

test('oneWin colours: exhausted -> error, off-pace -> warning, on-pace -> success', () => {
  const now = Date.now()
  const resetsAt = now + 3 * 3600_000
  const winOnPace = { kind: '5h' as const, used: 0.4, resetsAt }
  const winOffPace = { kind: '5h' as const, used: 0.8, resetsAt }
  const winFull = { kind: '7d' as const, used: 1.0, resetsAt }
  expect(oneWin(winOnPace, now).color).toBe('success')
  expect(oneWin(winOffPace, now).color).toBe('warning')
  expect(oneWin({ kind: '7d', used: 0.95, resetsAt }, now).color).toBe('warning')
  expect(oneWin(winFull, now).color).toBe('error')
  expect(oneWin(winFull, now).text).toContain('ETA now/')
})

test('oneWin: a stale window with used 1.0 is not exhausted', () => {
  const now = Date.now()
  expect(exhausted({ kind: '5h', used: 1.0, resetsAt: now - 10_000 }, now)).toBe(false)
  expect(exhausted({ kind: '5h', used: 1.0, resetsAt: now }, now)).toBe(false)
  expect(exhausted({ kind: '5h', used: 1.0, resetsAt: now + 10_000 }, now)).toBe(true)
  const c = oneWin({ kind: '5h', used: 1.0, resetsAt: now - 10_000 }, now)
  expect(c.color).toBe('success')
  expect(c.text).toContain('ETA -/now')
})

// --- bandRows tests (aligned layout) ---

const NOW_TEST = 1_800_000_000_000 // fixed timestamp for deterministic tests

type RowPart = { text: string; color?: string; dim?: boolean; bold?: boolean }

// Helper to join a row's text parts
function rowText(row: RowPart[]): string {
  return row.map(p => p.text).join('')
}

function getRow(rows: RowPart[][], index: number): RowPart[] {
  const row = rows[index]
  expect(row).toBeDefined()
  return row!
}

function findPart(row: RowPart[], labelPrefix: string): RowPart {
  const part = row.find(p => p.text.startsWith(labelPrefix))
  expect(part).toBeDefined()
  return part!
}

test('bandRows: Claude only (engine windows), head shown, aligned columns', () => {
  const snap = {
    effort: 'high',
    windows: [
      { kind: '5h' as const, used: 0.6, resetsAt: NOW_TEST + 2 * 3600_000 },
      { kind: '7d' as const, used: 0.4, resetsAt: NOW_TEST + 4 * 86400_000 },
    ],
    ctx: null,
  }
  const state = {}
  const rows = bandRows(snap, 'Opus 5.5 (subscription)', NOW_TEST, true, false, state)
  // head + 1 plan row = 2 rows
  expect(rows.length).toBe(2)
  // Row 0: head alone (no " | ")
  const headText = rowText(getRow(rows, 0))
  expect(headText.startsWith('Opus 5.5 (subscription) high')).toBe(true)
  expect(headText).not.toContain(' | ')
  // Row 1: Claude row (no indent)
  const row1 = getRow(rows, 1)
  const text = rowText(row1)
  expect(text).toContain('Claude')
  expect(text).toContain('5h pace 60/')
  expect(text).toContain('7d pace 40/')
  expect(text).toContain(' · ')
  // Claude label bold (current plan)
  expect(findPart(row1, 'Claude').bold).toBe(true)
})

test('bandRows: Claude engine windows empty, falls back to state subscription', () => {
  const snap = { effort: '', windows: [], ctx: null }
  const state = {
    subscription: {
      '5h': { utilization: 0.3, reset: Math.floor(NOW_TEST / 1000) + 3600 },
      '7d': { utilization: 0.5, reset: Math.floor(NOW_TEST / 1000) + 4 * 86400 },
    },
  }
  const rows = bandRows(snap, 'claude-sonnet-4', NOW_TEST, true, false, state)
  // head + 1 plan row = 2 rows
  expect(rows.length).toBe(2)
  // Row 0: head
  const headText = rowText(getRow(rows, 0))
  expect(headText).toContain('claude-sonnet-4')
  expect(headText).not.toContain(' | ')
  // Row 1: Claude row
  const row1 = getRow(rows, 1)
  const text = rowText(row1)
  expect(text).toContain('Claude')
  expect(text).toContain('5h pace 30/')
  expect(text).toContain('7d pace 50/')
})

test('bandRows: no Claude windows, Go row from state (head on row 1)', () => {
  const snap = { effort: '', windows: [], ctx: null }
  const state = {
    plans: {
      go: {
        '5h': { utilization: 0.14, reset: Math.floor(NOW_TEST / 1000) + 3 * 3600 },
        '7d': { utilization: 0.45, reset: Math.floor(NOW_TEST / 1000) + 5 * 86400 },
        '1mo': { utilization: 0.73, reset: Math.floor(NOW_TEST / 1000) + 26 * 86400 },
      },
    },
  }
  const rows = bandRows(snap, 'GLM5.3flash (Cloud, Go Plus, ≈360M вых.ток/мес)', NOW_TEST, true, false, state)
  // head + 1 plan row = 2 rows
  expect(rows.length).toBe(2)
  // Row 0: head alone
  const headText = rowText(getRow(rows, 0))
  expect(headText).toContain('GLM5.3flash')
  expect(headText).not.toContain(' | ')
  // Row 1: Go row (no indent, current plan = bold)
  const row1 = getRow(rows, 1)
  const text = rowText(row1)
  expect(text).toContain('Go ')
  expect(text).toContain('5h pace 14/')
  expect(text).toContain('7d pace 45/')
  expect(text).toContain('1mo pace 73/')
  // Go label bold (current plan)
  expect(findPart(row1, 'Go').bold).toBe(true)
})

test('bandRows: Claude row 1, z.ai row 2 from state', () => {
  const snap = {
    effort: '',
    windows: [{ kind: '5h' as const, used: 0.3, resetsAt: NOW_TEST + 3600 }],
    ctx: null,
  }
  const state = {
    plans: {
      zai: {
        '5h': { utilization: 0.2, reset: Math.floor(NOW_TEST / 1000) + 2 * 3600 },
        '7d': { utilization: 0.5, reset: Math.floor(NOW_TEST / 1000) + 4 * 86400 },
      },
    },
  }
  const rows = bandRows(snap, 'glm-5.3-flash-cloud-zai-direct', NOW_TEST, true, false, state)
  // head + 2 plan rows = 3 rows
  expect(rows.length).toBe(3)
  // Row 0: head
  const headText = rowText(getRow(rows, 0))
  expect(headText).toContain('glm-5.3-flash-cloud-zai-direct')
  expect(headText).not.toContain(' | ')
  // Row 1: Claude (not current plan, not bold)
  const row1 = getRow(rows, 1)
  const text1 = rowText(row1)
  expect(text1).toContain('Claude')
  expect(findPart(row1, 'Claude').bold).not.toBe(true)
  // Row 2: z.ai (current plan, bold)
  const row2 = getRow(rows, 2)
  const text2 = rowText(row2)
  expect(text2).toContain('z.ai')
  expect(findPart(row2, 'z.ai').bold).toBe(true)
})

test('bandRows: all five plans, Go is current, aligned columns', () => {
  const snap = {
    effort: '',
    windows: [{ kind: '5h' as const, used: 0.3, resetsAt: NOW_TEST + 3600 }],
    ctx: null,
  }
  const state = {
    plans: {
      fable: { '7d': { utilization: 0.4, reset: Math.floor(NOW_TEST / 1000) + 4 * 86400 } },
      go: { '5h': { utilization: 0.14, reset: Math.floor(NOW_TEST / 1000) + 3 * 3600 } },
      zai: { '5h': { utilization: 0.2, reset: Math.floor(NOW_TEST / 1000) + 2 * 3600 } },
      openrouter: { '1d': { utilization: 0.5, reset: Math.floor(NOW_TEST / 1000) + 86400 } },
    },
  }
  const rows = bandRows(snap, 'glm-5.3-flash-cloud-opencode-go-direct', NOW_TEST, true, false, state)
  // head + 5 plans = 6 rows
  expect(rows.length).toBe(6)
  // Row 0: head
  const headText = rowText(getRow(rows, 0))
  expect(headText).toContain('glm-5.3-flash-cloud-opencode-go-direct')
  expect(headText).not.toContain(' | ')
  // Row 1: Claude (from engine)
  expect(rowText(getRow(rows, 1))).toContain('Claude')
  // Row 2: Fable
  expect(rowText(getRow(rows, 2))).toContain('Fable')
  // Row 3: Go (bold, current plan)
  expect(findPart(getRow(rows, 3), 'Go').bold).toBe(true)
  // Row 4: z.ai
  expect(rowText(getRow(rows, 4))).toContain('z.ai')
  // Row 5: OpenRouter
  expect(rowText(getRow(rows, 5))).toContain('OpenRouter')
})

test('bandRows: ctx in head when showContext true', () => {
  const snap = {
    effort: '',
    windows: [{ kind: '5h' as const, used: 0.3, resetsAt: NOW_TEST + 3600 }],
    ctx: 34.7,
  }
  const state = {}
  const rows = bandRows(snap, 'Opus 5.5', NOW_TEST, true, true, state)
  // head + 1 plan row = 2 rows
  expect(rows.length).toBe(2)
  // Row 0: head with ctx
  const headText = rowText(getRow(rows, 0))
  expect(headText).toContain('ctx 35%')
  expect(headText).not.toContain(' | ')
  // ctx should be in head, not in plan row
  const planText = rowText(getRow(rows, 1))
  expect(planText).not.toContain('ctx')
  // Row 1: Claude with windows
  expect(planText).toContain('5h pace')
})

test('bandRows: no data, showContext false -> empty', () => {
  const snap = { effort: '', windows: [], ctx: null }
  const state = {}
  const rows = bandRows(snap, 'gpt-4', NOW_TEST, true, false, state)
  expect(rows.length).toBe(0)
})

test('bandRows: no data, showContext true -> row 1 with ctx in head', () => {
  const snap = { effort: '', windows: [], ctx: 34 }
  const state = {}
  const rows = bandRows(snap, 'gpt-4', NOW_TEST, true, true, state)
  expect(rows.length).toBe(1)
  const text = rowText(getRow(rows, 0))
  expect(text).toContain('ctx 34%')
})

test('bandRows: stale state file ignored', () => {
  const snap = { effort: '', windows: [], ctx: null }
  const staleTime = Math.floor((NOW_TEST - 7 * 3600_000) / 1000)
  const state = {
    updated: staleTime,
    plans: {
      go: { '5h': { utilization: 0.14, reset: Math.floor(NOW_TEST / 1000) + 3 * 3600 } },
    },
  }
  const rows = bandRows(snap, 'glm-5.3-flash-cloud-opencode-go-direct', NOW_TEST, true, false, state)
  expect(rows.length).toBe(0)
})

test('bandRows: showModel false hides head', () => {
  const snap = {
    effort: '',
    windows: [{ kind: '5h' as const, used: 0.3, resetsAt: NOW_TEST + 3600 }],
    ctx: null,
  }
  const state = {}
  const rows = bandRows(snap, 'claude-opus-5-5', NOW_TEST, false, false, state)
  expect(rows.length).toBe(1)
  const row0 = getRow(rows, 0)
  // Row starts with "Claude " (no head, no separator)
  expect(rowText(row0).startsWith('Claude ')).toBe(true)
  expect(findPart(row0, 'Claude').bold).toBe(true)
})

test('bandRows: aligned columns with missing kind in middle row', () => {
  // Claude has 5h and 7d; Go has only 7d and 1mo (missing 5h)
  const snap = {
    effort: '',
    windows: [
      { kind: '5h' as const, used: 0.6, resetsAt: NOW_TEST + 2 * 3600_000 },
      { kind: '7d' as const, used: 0.4, resetsAt: NOW_TEST + 4 * 86400_000 },
    ],
    ctx: null,
  }
  const state = {
    plans: {
      go: {
        '7d': { utilization: 0.45, reset: Math.floor(NOW_TEST / 1000) + 5 * 86400 },
        '1mo': { utilization: 0.73, reset: Math.floor(NOW_TEST / 1000) + 26 * 86400 },
      },
    },
  }
  const rows = bandRows(snap, 'glm-5.3-flash-cloud-opencode-go-direct', NOW_TEST, true, false, state)
  // head + 2 plan rows = 3 rows
  expect(rows.length).toBe(3)
  // Row 0: head
  const headText = rowText(getRow(rows, 0))
  expect(headText).toContain('glm-5.3-flash-cloud-opencode-go-direct')
  expect(headText).not.toContain(' | ')
  // Row 1: Claude
  const row1 = getRow(rows, 1)
  const text1 = rowText(row1)
  expect(text1).toContain('5h pace 60/')
  expect(text1).toContain('7d pace 40/')
  // Row 2: Go (no indent in new layout)
  const row2 = getRow(rows, 2)
  const text2 = rowText(row2)
  expect(text2).toContain('Go ')
  expect(text2.startsWith('Go ')).toBe(true) // no leading indent
  // Check alignment: Go's 7d should align with Claude's 7d
  expect(text2).toContain('7d pace 45/')
  expect(text2).toContain('1mo pace 73/')
  // Missing 5h column is spaces: Go's 7d cell starts where Claude's 7d cell starts
  expect(text2.indexOf('7d pace')).toBe(text1.indexOf('7d pace'))
})

test('bandRows: 1d kind appears between 5h and 7d', () => {
  const snap = { effort: '', windows: [], ctx: null }
  const state = {
    plans: {
      openrouter: {
        '5h': { utilization: 0.1, reset: Math.floor(NOW_TEST / 1000) + 3600 },
        '1d': { utilization: 0.5, reset: Math.floor(NOW_TEST / 1000) + 86400 },
        '7d': { utilization: 0.3, reset: Math.floor(NOW_TEST / 1000) + 4 * 86400 },
      },
    },
  }
  const rows = bandRows(snap, 'model (OpenRouter)', NOW_TEST, true, false, state)
  expect(rows.length).toBe(2)
  const text = rowText(getRow(rows, 1))
  // Order: 5h, 1d, 7d
  const idx5h = text.indexOf('5h pace')
  const idx1d = text.indexOf('1d pace')
  const idx7d = text.indexOf('7d pace')
  expect(idx5h).toBeLessThan(idx1d)
  expect(idx1d).toBeLessThan(idx7d)
})
// --- subscription usage endpoint ---

const USAGE = {
  five_hour: { utilization: 15.0, resets_at: '2026-11-04T11:00:00.110743+00:00' },
  seven_day: { utilization: 24.0, resets_at: '2026-11-10T05:00:00.110770+00:00' },
  seven_day_opus: null,
  limits: [
    { kind: 'session', percent: 15, resets_at: '2026-11-04T11:00:00+00:00', scope: null },
    { kind: 'weekly_all', percent: 24, resets_at: '2026-11-10T05:00:00+00:00', scope: null },
    { kind: 'weekly_scoped', percent: 31, resets_at: '2026-11-10T05:00:00.111041+00:00',
      scope: { model: { id: null, display_name: 'Fable' }, surface: null } },
  ],
}

test('oauthPlans: claude 5h/7d and the Fable weekly limit', () => {
  const p = oauthPlans(USAGE)
  expect(p.claude!['5h']!.utilization).toBe(0.15)
  expect(p.claude!['7d']!.reset).toBe(Date.parse('2026-11-10T05:00:00.110770+00:00') / 1000)
  expect(p.fable!['7d']!.utilization).toBe(0.31)
  expect(Object.keys(p).sort()).toEqual(['claude', 'fable'])
})

test('oauthPlans: junk gives no plans', () => {
  expect(oauthPlans(null)).toEqual({})
  expect(oauthPlans({ five_hour: { utilization: 'x' }, limits: 'no' })).toEqual({})
})

test('mergeState: endpoint plans over a stale file, Fable row drawn', () => {
  const now = Date.parse('2026-11-04T08:00:00Z')
  const stale = { updated: now / 1000 - 30000, plans: { go: { '7d': { utilization: 0.5, reset: now / 1000 + 3600 } } } }
  const state = mergeState(stale, oauthPlans(USAGE), now)
  expect(stateWins(state, 'go', now)).toEqual([])
  expect(stateWins(state, 'fable', now)[0]!.used).toBe(0.31)
  const rows = bandRows({ effort: '', windows: [], ctx: null }, 'claude-fable-5-1', now, true, false, state)
  expect(rows.map(r => r.map(p => p.text).join(''))[2]!.startsWith('Fable')).toBe(true)
})

test('bandRows: a single row is compact (no alignment padding)', () => {
  const now = Date.parse('2026-11-04T08:00:00Z')
  const snap = {
    effort: 'high',
    windows: [
      { kind: '5h' as const, used: 0.07, resetsAt: now + 3 * 3600_000 },
      { kind: '7d' as const, used: 0.23, resetsAt: now + 5 * 86400_000 },
    ],
    ctx: 4,
  }
  const rows = bandRows(snap, 'claude-opus-5-5', now, true, true, null)
  const text = rows[1]!.map(p => p.text).join('')
  expect(rows.length).toBe(2)
  expect(rowText(rows[0]!)).toBe('claude-opus-5-5 high ctx 4%')
  expect(text.startsWith('Claude 5h pace 7/')).toBe(true)
  expect(text.includes('  ')).toBe(false)
})

// --- v0.4 layout: head on its own line, gemini, status ---

const plain = (rows: RowPart[][]) => rows.map(rowText)
const SEC = Math.floor(NOW_TEST / 1000)
const claudeSnap = {
  effort: 'high',
  windows: [{ kind: '5h' as const, used: 0.1, resetsAt: NOW_TEST + 3 * 3600_000 }],
  ctx: 12,
}

test('bandRows: head is on its own line, never joined to a plan row', () => {
  const rows = plain(bandRows(claudeSnap, 'Opus 5.5 (subscription)', NOW_TEST, true, true, null))
  expect(rows.length).toBe(2)
  expect(rows[0]).toBe('Opus 5.5 (subscription) high ctx 12%')
  expect(rows[1]!.startsWith('Claude 5h pace')).toBe(true)
})

test('bandRows: gemini status-only row is aligned with the other labels', () => {
  const state = { plans: { gemini: { status: 'ok' } } }
  const rows = plain(bandRows(claudeSnap, 'gemini-3-pro', NOW_TEST, true, false, state))
  expect(rows.length).toBe(3)
  expect(rows[2]).toBe('Gemini ok')
  // Claude and Gemini labels have the same width: the first column starts at the same place
  expect(rows[1]!.indexOf('5h pace')).toBe(7)
  const withGo = plain(bandRows(claudeSnap, 'gemini-3-pro', NOW_TEST, true, false,
    { plans: { gemini: { status: 'ok' }, openrouter: { '1d': { utilization: 0.2, reset: SEC + 3600 } } } }))
  expect(withGo[3]).toBe('Gemini     ok') // padded to the OpenRouter label
})

test('bandRows: status follows the last window after " · "', () => {
  const state = { plans: { go: { '5h': { utilization: 0.14, reset: SEC + 3 * 3600 }, status: 'slow 5m' } } }
  const rows = plain(bandRows({ effort: '', windows: [], ctx: null }, 'x (Go)', NOW_TEST, true, false, state))
  expect(rows[1]!.endsWith(' · slow 5m')).toBe(true)
  expect(rows[1]!.startsWith('Go 5h pace 14/')).toBe(true)
})

test('bandRows: status colour is success for "ok", warning otherwise', () => {
  const state = { plans: { go: { status: 'slow 5m' }, gemini: { status: 'ok' } } }
  const rows = bandRows({ effort: '', windows: [], ctx: null }, 'x', NOW_TEST, false, false, state)
  expect(rows.length).toBe(2)
  expect(rows[0]!.find(p => p.text === 'slow 5m')!.color).toBe('warning')
  expect(rows[1]!.find(p => p.text === 'ok')!.color).toBe('success')
})

test('bandRows: on-pace cells lose their colour in a row with an exhausted cell', () => {
  const state = {
    plans: {
      go: {
        '5h': { utilization: 0.05, reset: SEC + 3 * 3600 },
        '7d': { utilization: 0.95, reset: SEC + 86400 },
        '1mo': { utilization: 1.0, reset: SEC + 10 * 86400 },
      },
      zai: { '5h': { utilization: 0.05, reset: SEC + 3 * 3600 } },
    },
  }
  const rows = bandRows({ effort: '', windows: [], ctx: null }, 'x', NOW_TEST, false, false, state)
  expect(rows.length).toBe(2)
  const cell = (r: number, k: string) => rows[r]!.find(p => p.text.startsWith(k + ' pace'))!
  expect(cell(0, '5h').color).toBeUndefined()
  expect(cell(0, '7d').color).toBe('warning')
  expect(cell(0, '1mo').color).toBe('error')
  expect(cell(1, '5h').color).toBe('success')
})

test('bandRows: a stale full window does not drop the green of its row', () => {
  const state = {
    plans: {
      go: {
        '5h': { utilization: 1.0, reset: SEC - 10 },
        '7d': { utilization: 0.05, reset: SEC + 86400 },
      },
    },
  }
  const rows = bandRows({ effort: '', windows: [], ctx: null }, 'x', NOW_TEST, false, false, state)
  expect(rows[0]!.find(p => p.text.startsWith('7d pace'))!.color).toBe('success')
  expect(rows[0]!.find(p => p.text.startsWith('5h pace'))!.color).toBe('success')
})

test('bandRows: status is cut to 40 characters', () => {
  const state = { plans: { gemini: { status: 'x'.repeat(60) } } }
  const rows = plain(bandRows({ effort: '', windows: [], ctx: null }, 'x', NOW_TEST, false, false, state))
  expect(rows).toEqual(['Gemini ' + 'x'.repeat(40)])
})

test('planOf: gemini, but a Gemini model through OpenRouter is openrouter', () => {
  expect(planOf('gemini-3-pro')).toBe('gemini')
  expect(planOf('Gemini 3 Pro (free tier)')).toBe('gemini')
  expect(planOf('google/gemini-3-pro (OpenRouter)')).toBe('openrouter')
  expect(planOf('openrouter-gemini-3')).toBe('openrouter')
})

test('bandRows: a single plan row has no double spaces', () => {
  const rows = plain(bandRows(claudeSnap, 'claude-opus-5-5', NOW_TEST, false, false, null))
  expect(rows.length).toBe(1)
  expect(rows[0]!.includes('  ')).toBe(false)
  const status = plain(bandRows({ effort: '', windows: [], ctx: null }, 'x', NOW_TEST, false, false, { plans: { gemini: { status: 'ok' } } }))
  expect(status).toEqual(['Gemini ok'])
})

// --- shared layout cases (the Python tests run the same file) ---

type Case = {
  name: string
  now_ms: number
  engine: { kind: string; used: number; reset_ms: number }[]
  state: unknown
  model_id: string
  label: string
  effort: string
  ctx: number | null
  showModel: boolean
  showContext: boolean
  rows: string[]
}

// Times of day are masked so the rows do not depend on the time zone (the Python test masks the same way).
const mask = (t: string) => t
  .replace(/\b(Sun|Mon|Tue|Wed|Thu|Fri|Sat)-/g, 'Www-')
  .replace(/\b\d\d:\d\d\b/g, '##:##')
  .replace(/\b\d\d\.\d\d\b/g, '##.##')

for (const c of cases as Case[]) {
  test(`layout case: ${c.name}`, () => {
    const snap = {
      effort: c.effort,
      windows: c.engine.map(e => ({ kind: e.kind as Kind, used: e.used, resetsAt: e.reset_ms })),
      ctx: c.ctx,
    }
    const rows = bandRows(snap, c.label, c.now_ms, c.showModel, c.showContext, c.state)
    expect(plain(rows).map(mask)).toEqual(c.rows)
  })
}

// --- readOauth ---

const OAUTH_BODY = {
  five_hour: { utilization: 15.0, resets_at: '2026-11-04T11:00:00+00:00' },
  seven_day: { utilization: 24.0, resets_at: '2026-11-10T05:00:00+00:00' },
  limits: [
    { kind: 'weekly_scoped', percent: 31, resets_at: '2026-11-10T05:00:00+00:00',
      scope: { model: { id: null, display_name: 'Fable' }, surface: null } },
  ],
}

function fakeEngine(auth: unknown) {
  const calls: { url: string; opts: any }[] = []
  let authorized = 0
  const $ = {
    session: { authorize: async () => { authorized++; return auth } },
    http: {
      fetch: async (url: string, opts: any) => {
        calls.push({ url, opts })
        return { ok: true, text: JSON.stringify(OAUTH_BODY) }
      },
    },
  }
  return { $: $ as any, calls, authorized: () => authorized }
}

test('readOauth: fetches the usage endpoint with the engine handle and parses plans', async () => {
  resetOauthCache()
  const e = fakeEngine({ kind: 'bearer', handle: 'h' })
  const plans = await readOauth(e.$)
  expect(e.calls.length).toBe(1)
  expect(e.calls[0]!.url).toBe('https://api.anthropic.com/api/oauth/usage')
  expect(e.calls[0]!.opts.auth).toBe('h')
  expect(e.calls[0]!.opts.headers['anthropic-beta']).toBe('oauth-2025-04-20')
  expect(plans.claude!['5h']!.utilization).toBe(0.15)
  expect(plans.claude!['7d']!.utilization).toBe(0.24)
  expect(plans.fable!['7d']!.utilization).toBe(0.31)
  // a second call within 5 minutes uses the cache
  const again = await readOauth(e.$)
  expect(e.calls.length).toBe(1)
  expect(again).toEqual(plans)
  resetOauthCache()
})

test('readOauth: no first-party login gives no plans and no fetch', async () => {
  resetOauthCache()
  const e = fakeEngine(null)
  expect(await readOauth(e.$)).toEqual({})
  expect(e.calls.length).toBe(0)
  resetOauthCache()
})


// --- sub-agents line ---

test('agentsRow counts pairs and strips prefixes; empty when none', () => {
  expect(agentsRow([['worker-coder', 'glm-5.3-flash'], ['Explore', null], ['Explore', null], ['worker-verifier', 'claude-sonnet-5-5']]))
    .toBe('agents coder:glm-5.3-flash, Explore:starting x2, verifier:sonnet-5-5')
  expect(agentsRow([])).toBe('')
})

test('lastModel takes the last assistant model, skips synthetic and junk', () => {
  const lines = [
    JSON.stringify({ type: 'assistant', message: { role: 'assistant', model: 'glm-5.3-flash' } }),
    'not json "assistant"',
    JSON.stringify({ type: 'assistant', message: { role: 'assistant', model: '<synthetic>' } }),
  ]
  expect(lastModel(lines.join('\n'))).toBe('glm-5.3-flash')
  expect(lastModel(JSON.stringify({ type: 'user' }))).toBe(null)
})

test('readAgents lists transcripts written in the last 120 s, with type and model', async () => {
  const now = 1_800_000_000_000
  const files: Record<string, { mtimeMs: number; text: string }> = {
    '/t/sid/subagents/agent-a.jsonl': { mtimeMs: now - 5_000, text: JSON.stringify({ message: { role: 'assistant', model: 'm1' } }) + '\n"assistant"' },
    '/t/sid/subagents/agent-a.meta.json': { mtimeMs: now, text: JSON.stringify({ agentType: 'worker-coder' }) },
    '/t/sid/subagents/agent-b.jsonl': { mtimeMs: now - 1_000, text: JSON.stringify({ type: 'user' }) },
    '/t/sid/subagents/agent-c.jsonl': { mtimeMs: now - 600_000, text: '' },
  }
  const $ = {
    fs: {
      list: async () => Object.keys(files).map(p => ({ name: p.split('/').pop()!, kind: 'file', size: 1 })),
      stat: async (p: string) => ({ kind: 'file', size: 1, mtimeMs: files[p]!.mtimeMs, isLink: false }),
      read: async (p: string) => {
        if (files[p] === undefined) throw new Error('missing')
        return files[p]!.text
      },
    },
  } as never
  setAgentsDir('/t/sid.jsonl', 'sid')
  expect(await readAgents($, now)).toEqual([['worker-coder', 'm1'], ['agent', null]])
})
