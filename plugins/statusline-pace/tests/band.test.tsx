import { expect, test } from 'claude-code/testing'
import {
  bandRows,
  fmt,
  offPace,
  oneWin,
  planOf,
  shortLabel,
  stateWins,
  winsOf,
} from '../hooks/register'

// --- fmt tests ---

test('fmt 5h returns HH:MM', () => {
  const ms = new Date(2027, 0, 15, 14, 30).getTime()
  expect(fmt('5h', ms)).toBe('14:30')
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

test('stateWins go extracts 5h/7d/1mo in order', () => {
  const state = {
    plans: {
      go: {
        '5h': { utilization: 0.14, reset: Math.floor(NOW / 1000) + 3 * 3600 },
        '7d': { utilization: 0.45, reset: Math.floor(NOW / 1000) + 5 * 86400 },
        '1mo': { utilization: 0.73, reset: Math.floor(NOW / 1000) + 26 * 86400 },
      },
    },
  }
  const wins = stateWins(state, 'go')
  expect(wins.length).toBe(3)
  expect(wins[0]).toEqual({ kind: '5h', used: 0.14, resetsAt: expect.any(Number) })
  expect(wins[1]).toEqual({ kind: '7d', used: 0.45, resetsAt: expect.any(Number) })
  expect(wins[2]).toEqual({ kind: '1mo', used: 0.73, resetsAt: expect.any(Number) })
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

test('oneWin colours: off-pace -> error, on-pace -> success', () => {
  const now = Date.now()
  const resetsAt = now + 3 * 3600_000
  const winOnPace = { kind: '5h' as const, used: 0.4, resetsAt }
  const winOffPace = { kind: '5h' as const, used: 0.8, resetsAt }
  expect(oneWin(winOnPace, now).color).toBe('success')
  expect(oneWin(winOffPace, now).color).toBe('error')
})

// --- bandRows tests (new multi-row) ---

const NOW_TEST = 1_800_000_000_000 // fixed timestamp for deterministic tests

type RowPart = { text: string; color?: string; dim?: boolean; bold?: boolean }

// Helper to find a part by text and assert it exists
function findPart(row: RowPart[], text: string): RowPart {
  const part = row.find(p => p.text === text)
  expect(part).toBeDefined()
  return part!
}

function getRow(rows: RowPart[][], index: number): RowPart[] {
  const row = rows[index]
  expect(row).toBeDefined()
  return row!
}

test('bandRows: Claude only (engine windows), head shown', () => {
  const snap = {
    effort: 'high',
    windows: [
      { kind: '5h' as const, used: 0.6, resetsAt: NOW_TEST + 2 * 3600_000 },
      { kind: '7d' as const, used: 0.4, resetsAt: NOW_TEST + 4 * 86400_000 },
    ],
    ctx: null,
  }
  const state = {}
  // Use a proper display name like the engine would provide
  const rows = bandRows(snap, 'Opus 5.5 (subscription)', NOW_TEST, true, false, state)
  expect(rows.length).toBe(1)
  const row0 = getRow(rows, 0)
  const texts = row0.map(p => p.text)
  // shortLabel keeps "subscription" tag
  expect(texts[0]).toBe('Opus 5.5 (subscription) high')
  expect(texts[1]).toBe(' | ')
  expect(texts[2]).toBe('Claude')
  expect(texts[3]).toBe(' ')
  expect(texts[4]).toContain('5h pace 60/')
  expect(texts[5]).toBe(' · ')
  expect(texts[6]).toContain('7d pace 40/')
  // Claude plan label should be bold
  expect(findPart(row0, 'Claude').bold).toBe(true)
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
  expect(rows.length).toBe(1)
  const row0 = getRow(rows, 0)
  const texts = row0.map(p => p.text).join('')
  expect(texts).toContain('Claude')
  expect(texts).toContain('5h pace 30/')
  expect(texts).toContain('7d pace 50/')
})

test('bandRows: Claude row 1, Go row 2 from state', () => {
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
  // Use a proper display name for the Go model
  const rows = bandRows(snap, 'GLM5.3flash (Cloud, Go Plus, ≈360M вых.ток/мес)', NOW_TEST, true, false, state)
  expect(rows.length).toBe(2)
  const row0 = getRow(rows, 0)
  const row1 = getRow(rows, 1)
  // Row 1: Claude (no windows, but head shown because row 2 exists)
  expect(row0.map(p => p.text).join('')).toContain('GLM5.3flash')
  // Row 2: Go
  const row2Text = row1.map(p => p.text).join('')
  expect(row2Text).toContain('Go')
  expect(row2Text).toContain('5h pace 14/')
  expect(row2Text).toContain('7d pace 45/')
  expect(row2Text).toContain('1mo pace 73/')
  // Go label should be bold (current plan)
  expect(findPart(row1, 'Go').bold).toBe(true)
  // Claude label should NOT be bold (no Claude windows, so no Claude label in row 1)
  const claudePart = row0.find(p => p.text === 'Claude')
  expect(claudePart).toBeUndefined()
})

test('bandRows: Claude row 1, z.ai row 2 from state', () => {
  const snap = { effort: '', windows: [], ctx: null }
  const state = {
    plans: {
      zai: {
        '5h': { utilization: 0.2, reset: Math.floor(NOW_TEST / 1000) + 2 * 3600 },
        '7d': { utilization: 0.5, reset: Math.floor(NOW_TEST / 1000) + 4 * 86400 },
      },
    },
  }
  const rows = bandRows(snap, 'glm-5.3-flash-cloud-zai-direct', NOW_TEST, true, false, state)
  expect(rows.length).toBe(2)
  const row1 = getRow(rows, 1)
  const row2Text = row1.map(p => p.text).join('')
  expect(row2Text).toContain('z.ai')
  expect(row2Text).toContain('5h pace 20/')
  expect(row2Text).toContain('7d pace 50/')
  // z.ai label should be bold
  expect(findPart(row1, 'z.ai').bold).toBe(true)
})

test('bandRows: all three plans, Go is current', () => {
  const snap = {
    effort: '',
    windows: [{ kind: '5h' as const, used: 0.3, resetsAt: NOW_TEST + 3600 }],
    ctx: null,
  }
  const state = {
    plans: {
      go: { '5h': { utilization: 0.14, reset: Math.floor(NOW_TEST / 1000) + 3 * 3600 } },
      zai: { '5h': { utilization: 0.2, reset: Math.floor(NOW_TEST / 1000) + 2 * 3600 } },
    },
  }
  const rows = bandRows(snap, 'glm-5.3-flash-cloud-opencode-go-direct', NOW_TEST, true, false, state)
  expect(rows.length).toBe(3)
  const row0 = getRow(rows, 0)
  const row1 = getRow(rows, 1)
  const row2 = getRow(rows, 2)
  // Row 1: Claude (from engine)
  expect(row0.map(p => p.text).join('')).toContain('Claude')
  // Row 2: Go (bold)
  expect(findPart(row1, 'Go').bold).toBe(true)
  // Row 3: z.ai (not bold)
  expect(findPart(row2, 'z.ai').bold).toBe(false)
})

test('bandRows: no Claude windows, no other plans, showContext false -> empty', () => {
  const snap = { effort: '', windows: [], ctx: null }
  const state = {}
  const rows = bandRows(snap, 'gpt-4', NOW_TEST, true, false, state)
  expect(rows.length).toBe(0)
})

test('bandRows: no Claude windows, no other plans, showContext true -> row 1 with ctx', () => {
  const snap = { effort: '', windows: [], ctx: 34 }
  const state = {}
  const rows = bandRows(snap, 'gpt-4', NOW_TEST, true, true, state)
  expect(rows.length).toBe(1)
  const row0 = getRow(rows, 0)
  expect(row0.map(p => p.text).join('')).toContain('ctx 34%')
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
  expect(row0.length).toBeGreaterThan(0)
  // When showModel=false and there are Claude windows, row starts with "Claude" (no head, no separator)
  expect(row0[0]!.text).toBe('Claude')
  expect(findPart(row0, 'Claude').bold).toBe(true)
})

test('bandRows: separators are " · " between windows', () => {
  const snap = {
    effort: '',
    windows: [
      { kind: '5h' as const, used: 0.3, resetsAt: NOW_TEST + 3600 },
      { kind: '7d' as const, used: 0.5, resetsAt: NOW_TEST + 4 * 86400_000 },
    ],
    ctx: null,
  }
  const state = {}
  const rows = bandRows(snap, 'claude-opus-5-5', NOW_TEST, true, false, state)
  const row0 = getRow(rows, 0)
  const text = row0.map(p => p.text).join('')
  // Should have " · " between the two windows
  expect(text).toContain(' · ')
})