import { expect, test } from 'claude-code/testing'
import {
  bandTexts,
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

test('planOf claude/opus/sonnet/haiku returns claude', () => {
  expect(planOf('claude-opus-5-5')).toBe('claude')
  expect(planOf('claude-sonnet-4')).toBe('claude')
  expect(planOf('claude-haiku-3')).toBe('claude')
  expect(planOf('opus-5')).toBe('claude')
})

test('planOf subscription in label returns claude', () => {
  expect(planOf('Model (subscription, z.ai)')).toBe('claude')
})

test('planOf z.ai direct returns empty', () => {
  expect(planOf('glm-5.3-flash-cloud-zai-direct')).toBe('')
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

test('offPace 1mo: (0.73, 0.13) true — leads by >5pp', () => {
  expect(offPace('1mo', 0.73, 0.13)).toBe(true)
})

// --- stateWins tests ---

test('stateWins go extracts 5h/7d/1mo in order', () => {
  const now = Date.now()
  const state = {
    plans: {
      go: {
        '5h': { utilization: 0.14, reset: Math.floor(now / 1000) + 3 * 3600 },
        '7d': { utilization: 0.45, reset: Math.floor(now / 1000) + 5 * 86400 },
        '1mo': { utilization: 0.73, reset: Math.floor(now / 1000) + 26 * 86400 },
      },
    },
  }
  const wins = stateWins(state, 'go')
  expect(wins.length).toBe(3)
  expect(wins[0]).toEqual({ kind: '5h', used: 0.14, resetsAt: expect.any(Number) })
  expect(wins[1]).toEqual({ kind: '7d', used: 0.45, resetsAt: expect.any(Number) })
  expect(wins[2]).toEqual({ kind: '1mo', used: 0.73, resetsAt: expect.any(Number) })
})

test('stateWins claude falls back to subscription', () => {
  const now = Date.now()
  const state = {
    subscription: {
      '5h': { utilization: 0.6, reset: Math.floor(now / 1000) + 2 * 3600 },
      '7d': { utilization: 0.4, reset: Math.floor(now / 1000) + 4 * 86400 },
    },
  }
  const wins = stateWins(state, 'claude')
  expect(wins.length).toBe(2)
  expect(wins[0]!.kind).toBe('5h')
  expect(wins[1]!.kind).toBe('7d')
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

// --- bandTexts tests ---

test('bandTexts go snap with 3 windows renders separators and 1mo error', async () => {
  const now = Date.now()
  const snap = {
    effort: '',
    windows: [
      { kind: '5h' as const, used: 0.14, resetsAt: now + 3 * 3600_000 },
      { kind: '7d' as const, used: 0.45, resetsAt: now + 5 * 86400_000 },
      { kind: '1mo' as const, used: 0.73, resetsAt: now + 26 * 86400_000 },
    ],
    ctx: null,
  }
  const parts = await bandTexts(snap, 'GLM5.3flash (Cloud, Go Plus, $ BEST, ≈360M вых.ток/мес)', now, true, false)
  const texts = parts.map((p) => p.text)
  // head should be shortLabel
  expect(texts[0]).toBe('GLM5.3flash (Go Plus, ≈360M вых.ток/мес)')
  // separators
  expect(texts[1]).toBe(' | ')
  expect(texts[3]).toBe(' · ')
  expect(texts[5]).toBe(' · ')
  // 1mo should be error coloured
  const moPart = parts.find((p) => p.text.includes('1mo pace'))
  expect(moPart?.color).toBe('error')
})

test('bandTexts empty windows and showContext false -> empty parts', async () => {
  const now = Date.now()
  const snap = { effort: '', windows: [], ctx: null }
  const parts = await bandTexts(snap, 'gpt-4', now, true, false)
  expect(parts.length).toBe(0)
})

test('bandTexts empty windows and showContext true -> only ctx', async () => {
  const now = Date.now()
  const snap = { effort: '', windows: [], ctx: 34 }
  const parts = await bandTexts(snap, 'gpt-4', now, true, true)
  expect(parts.length).toBe(1)
  expect(parts[0]!.text).toBe(' ctx 34%')
  expect(parts[0]!.dim).toBe(true)
})

test('bandTexts head uses shortLabel for long model', async () => {
  const now = Date.now()
  const snap = {
    effort: 'high',
    windows: [{ kind: '5h' as const, used: 0.5, resetsAt: now + 3600_000 }],
    ctx: null,
  }
  const parts = await bandTexts(snap, 'GLM5.3flash (Cloud, Go Plus, ≈360M вых.ток/мес)', now, true, false)
  expect(parts[0]!.text).toBe('GLM5.3flash (Go Plus, ≈360M вых.ток/мес) high')
})