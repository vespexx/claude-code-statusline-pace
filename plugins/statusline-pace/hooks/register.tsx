import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, SessionRateLimit } from 'claude-code'

import type { Kind, Snap, Win } from '../types'

// statusline-pace: the subscription pace as a band above the prompt.
// v0.3: aligned columns, ctx in head, 1d kind, fable & openrouter plans.
// Kind order: 5h, 1d, 7d, 1mo.
// Plan order: claude, fable, go, zai, openrouter. Claude and per-model weekly limits (Fable) also come from
// the subscription usage endpoint, read with the engine-held credential (the token never reaches the plugin).

const snap = atom({ plugin: 'statusline-pace', key: 'snap' } as const, null, {
  shape: 'snap-3',
})

const LENGTH: Record<Kind, number> = {
  '5h': 5 * 3600_000,
  '1d': 86400_000,
  '7d': 7 * 86400_000,
  '1mo': 30 * 86400_000,
}

const ENGINE_KINDS: Record<string, Kind> = {
  five_hour: '5h',
  seven_day: '7d',
}

const WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const PLAN_TAGS = new Set(['Go', 'Go Plus', 'subscription', 'free tier', 'Fable', 'OpenRouter'])

const pad = (n: number) => String(n).padStart(2, '0')

// 5h/1d show `HH:MM`, 7d shows `Ddd-HH:MM` (local), 1mo shows `DD.MM` (1-indexed month).
// Callers guard that `ms` is finite.
export function fmt(kind: Kind, ms: number): string {
  const d = new Date(ms)
  if (kind === '5h' || kind === '1d') {
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`
  }
  if (kind === '7d') {
    return `${WEEK[d.getDay()]}-${pad(d.getHours())}:${pad(d.getMinutes())}`
  }
  // 1mo
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}`
}

export function winsOf(rows: readonly SessionRateLimit[]): Win[] {
  const wins: Win[] = []
  for (const row of rows) {
    const kind = ENGINE_KINDS[row.kind]
    if (kind === undefined || row.resetsAt === undefined) continue
    const resetsAt = Date.parse(row.resetsAt)
    if (!Number.isFinite(resetsAt)) continue
    wins.push({ kind, used: Math.max(0, row.percentUsed) / 100, resetsAt })
  }
  return wins
}

// Mirrors statusline.py label_items: split on ',' inside parentheses.
export function labelItems(label: string): [string, string[]] {
  const trimmed = label.trim()
  const m = trimmed.match(/^([^(]+)\s*\((.*)\)\s*$/)
  if (!m || m[1] === undefined) return [trimmed, []]
  const name = m[1].trim()
  const inner = m[2] ?? ''
  const items = inner.split(',').map(s => s.trim()).filter(s => s !== '')
  return [name, items]
}

// Mirrors statusline.py plan_of: takes the whole /model entry string.
// Returns 'claude', 'fable', 'go', 'zai', 'openrouter', or ''.
export function planOf(model: string): 'claude' | 'fable' | 'go' | 'zai' | 'openrouter' | '' {
  const s = model.toLowerCase()
  const [, items] = labelItems(model)
  const itemSet = new Set(items)
  // fable check before claude
  if (s.includes('fable') || itemSet.has('Fable')) {
    return 'fable'
  }
  // openrouter check before claude
  if (s.includes('openrouter') || itemSet.has('OpenRouter')) {
    return 'openrouter'
  }
  if (s.includes('opencode-go') || itemSet.has('Go') || itemSet.has('Go Plus')) {
    return 'go'
  }
  // zai check before claude: "zai" in id or label item starting with "z.ai"
  if (s.includes('zai') || items.some(i => i.startsWith('z.ai'))) {
    return 'zai'
  }
  if (itemSet.has('subscription') || s.includes('claude') || s.includes('opus') || s.includes('sonnet') || s.includes('haiku')) {
    return 'claude'
  }
  return ''
}

// Mirrors statusline.py short_label.
export function shortLabel(model: string): string {
  const [name, items] = labelItems(model)
  const keep = items.filter(i => PLAN_TAGS.has(i) || i.startsWith('z.ai') || i.startsWith('≈'))
  return keep.length > 0 ? `${name} (${keep.join(', ')})` : name
}

const STALE_THRESHOLD_MS = 21_600_000 // 6 hours

function isStateStale(state: unknown, now: number = Date.now()): boolean {
  if (typeof state !== 'object' || state === null) return false
  const stateObj = state as Record<string, unknown>
  const updated = stateObj.updated
  if (typeof updated !== 'number' || !Number.isFinite(updated)) return false
  return now - updated * 1000 > STALE_THRESHOLD_MS
}

// Mirrors statusline.py state_windows. Supports 'claude', 'fable', 'go', 'zai', 'openrouter'.
// Stale file (updated > 6h ago) is treated as no data.
export function stateWins(state: unknown, plan: 'claude' | 'fable' | 'go' | 'zai' | 'openrouter', now: number = Date.now()): Win[] {
  if (typeof state !== 'object' || state === null) return []
  if (isStateStale(state, now)) return []
  const stateObj = state as Record<string, unknown>
  const plans = stateObj.plans
  const plansObj = (typeof plans === 'object' && plans !== null) ? plans as Record<string, unknown> : {}
  const src = plansObj[plan]
  if (typeof src !== 'object' || src === null || Object.keys(src).length === 0) {
    // Claude fallback to subscription
    if (plan === 'claude') {
      const sub = stateObj.subscription
      if (typeof sub === 'object' && sub !== null) {
        return extractWins(sub as Record<string, unknown>)
      }
    }
    return []
  }
  return extractWins(src as Record<string, unknown>)
}

function extractWins(src: Record<string, unknown>): Win[] {
  const out: Win[] = []
  const order: Kind[] = ['5h', '1d', '7d', '1mo']
  for (const kind of order) {
    const x = src[kind]
    if (typeof x !== 'object' || x === null) continue
    const xObj = x as Record<string, unknown>
    const utilization = xObj.utilization
    const reset = xObj.reset
    if (typeof utilization !== 'number' || typeof reset !== 'number') continue
    if (!Number.isFinite(utilization) || !Number.isFinite(reset)) continue
    out.push({ kind, used: utilization, resetsAt: reset * 1000 })
  }
  return out
}

// Mirrors statusline.py off_pace.
// 5h: used > max(1.5 * elapsed, 0.1) or used > 0.75
// 1d/7d/1mo: used >= 0.9 OR used > elapsed + 0.05
export function offPace(kind: Kind, util: number, frac: number): boolean {
  if (kind === '5h') {
    return util > Math.max(1.5 * frac, 0.1) || util > 0.75
  }
  return util >= 0.9 || util > frac + 0.05
}

// One window part with colour from offPace.
export function oneWin(win: Win, now: number) {
  const left = win.resetsAt - now
  const stale = left <= 0
  const util = stale ? 0 : win.used
  const frac = stale ? 0 : Math.min(1, Math.max(0, 1 - left / LENGTH[win.kind]))
  const at = now + ((1 - util) / util) * frac * LENGTH[win.kind]
  const out = util >= 1 ? 'now' : util <= 0 || frac <= 0 || at >= win.resetsAt ? '-' : fmt(win.kind, at)
  const color = offPace(win.kind, util, frac) ? 'error' : 'success'
  const usedPct = Math.floor(util * 100 + 1e-9)
  const text = `${win.kind} pace ${usedPct}/${Math.round(frac * 100)}% ETA ${out}/${stale ? 'now' : fmt(win.kind, win.resetsAt)}`
  return { text, color }
}

type Part = { text: string; color?: string; dim?: boolean; bold?: boolean }

const PLAN_NAME = { claude: 'Claude', fable: 'Fable', go: 'Go', zai: 'z.ai', openrouter: 'OpenRouter' } as const
const PLAN_ORDER = ['claude', 'fable', 'go', 'zai', 'openrouter'] as const
const KIND_ORDER: Kind[] = ['5h', '1d', '7d', '1mo']

// The band as aligned rows of parts. Row 1 starts with the head
// (`<model> <effort> ctx N%` + ' | '); later rows are indented to the same
// column. Each row: the plan label padded to the longest one, then one
// column per kind (5h, 1d, 7d, 1mo) that any row has, each as wide as its
// longest cell. A gap of 3 before every column but the first: ' · ' when
// the row has this cell and an earlier one, else spaces. Claude windows come
// from the engine, else the file; the other plans only from the file.
export function bandRows(
  s: Snap | null,
  model: string,
  now: number,
  showModel: boolean,
  showContext: boolean,
  state: unknown
): Part[][] {
  const current = planOf(model)
  const engine = s?.windows ?? []
  const plans = PLAN_ORDER
    .map(plan => ({ plan, wins: plan === 'claude' && engine.length > 0 ? engine : stateWins(state, plan, now) }))
    .filter(r => r.wins.length > 0)
  const ctx = showContext && s !== null && s.ctx !== null ? ` ctx ${Math.round(s.ctx)}%` : ''
  const short = shortLabel(model)
  const effort = s?.effort ?? ''
  const head = showModel && short !== '' ? `${short}${effort !== '' ? ' ' + effort : ''}${ctx}` : ''
  if (plans.length === 0) return head !== '' && ctx !== '' ? [[{ text: head }]] : []

  const cells = plans.map(r => new Map(r.wins.map(w => [w.kind, oneWin(w, now)])))
  const kinds = KIND_ORDER.filter(k => cells.some(c => c.has(k)))
  const width = new Map(kinds.map(k => [k, Math.max(...cells.map(c => c.get(k)?.text.length ?? 0))]))
  const labelWidth = Math.max(...plans.map(r => PLAN_NAME[r.plan].length))
  const prefix = head !== '' ? head + ' | ' : ''

  return plans.map((r, i) => {
    const parts: Part[] = [
      { text: i === 0 ? prefix : ' '.repeat(prefix.length) },
      { text: PLAN_NAME[r.plan], bold: r.plan === current },
      { text: ' '.repeat(labelWidth - PLAN_NAME[r.plan].length + 1) },
    ]
    let seen = false
    kinds.forEach((k, ki) => {
      const cell = cells[i]!.get(k)
      if (ki > 0) parts.push({ text: cell !== undefined && seen ? ' · ' : '   ', dim: true })
      parts.push(cell ?? { text: '' }, { text: ' '.repeat(width.get(k)! - (cell?.text.length ?? 0)) })
      if (cell !== undefined) seen = true
    })
    return trimRow(parts)
  })
}

// Drop trailing spaces and empty parts so a row ends at its last cell.
function trimRow(parts: Part[]): Part[] {
  const out = parts.filter(p => p.text !== '')
  while (out.length > 0 && out[out.length - 1]!.text.trim() === '') out.pop()
  return out
}

type Plans = Record<string, Record<string, { utilization: number; reset: number }>>

// The windows of Anthropic's subscription usage endpoint (the one /usage
// reads): `five_hour` / `seven_day` -> claude 5h/7d, and each per-model
// weekly limit (`limits[]`, kind `weekly_scoped`, e.g. Fable) -> a plan named
// after the model. Utilization 0..1, reset epoch seconds, as in the file.
export function oauthPlans(body: unknown): Plans {
  const out: Plans = {}
  if (typeof body !== 'object' || body === null) return out
  const b = body as Record<string, unknown>
  const put = (plan: string, kind: Kind, percent: unknown, resetsAt: unknown) => {
    const reset = typeof resetsAt === 'string' ? Date.parse(resetsAt) / 1000 : NaN
    if (typeof percent !== 'number' || !Number.isFinite(percent) || !Number.isFinite(reset)) return
    out[plan] = { ...out[plan], [kind]: { utilization: Math.max(0, percent) / 100, reset } }
  }
  for (const [key, kind] of [['five_hour', '5h'], ['seven_day', '7d']] as const) {
    const w = b[key] as Record<string, unknown> | null | undefined
    if (w) put('claude', kind, w.utilization, w.resets_at)
  }
  for (const l of Array.isArray(b.limits) ? b.limits : []) {
    const name = (l as { scope?: { model?: { display_name?: unknown } } })?.scope?.model?.display_name
    if ((l as { kind?: unknown }).kind === 'weekly_scoped' && typeof name === 'string') {
      put(name.toLowerCase(), '7d', (l as { percent?: unknown }).percent, (l as { resets_at?: unknown }).resets_at)
    }
  }
  return out
}

// The windows file with the endpoint's plans laid over it. A stale file
// keeps no plans of its own; the endpoint's are fresh by construction.
export function mergeState(file: unknown, oauth: Plans, now: number): unknown {
  if (Object.keys(oauth).length === 0) return file
  const f = typeof file === 'object' && file !== null && !isStateStale(file, now) ? file as Record<string, unknown> : {}
  const plans = typeof f.plans === 'object' && f.plans !== null ? f.plans as Plans : {}
  return { ...f, updated: now / 1000, plans: { ...plans, ...oauth } }
}

// The endpoint, at most every 5 minutes. The engine holds the credential and
// sets the header itself (`$.session.authorize`): the token never reaches
// this plugin. No first-party login (API key, gateway, 3P) -> no plans.
let oauthCache: { at: number; plans: Plans } = { at: 0, plans: {} }

async function readOauth($: EngineInterface): Promise<Plans> {
  const now = Date.now()
  if (now - oauthCache.at < 300_000) return oauthCache.plans
  oauthCache = { at: now, plans: oauthCache.plans }
  try {
    const auth = await $.session.authorize()
    if (auth === null || auth.kind !== 'bearer') return (oauthCache.plans = {})
    const r = await $.http.fetch('https://api.anthropic.com/api/oauth/usage', {
      auth: auth.handle,
      headers: { 'anthropic-beta': 'oauth-2025-04-20' },
    })
    if (r.ok) oauthCache.plans = oauthPlans(JSON.parse(r.text))
  } catch { /* keep the last good answer */ }
  return oauthCache.plans
}

// Cache state file read for 30s.
let stateCache: { at: number; data: unknown | null } = { at: 0, data: null }

async function readStateFile($: EngineInterface, stateFile: string): Promise<unknown | null> {
  if (stateFile === '') return null
  const now = Date.now()
  if (now - stateCache.at < 30_000 && stateCache.data !== null) {
    return stateCache.data
  }
  try {
    let path = stateFile
    if (path.startsWith('~/')) {
      const home = await $.env.get('HOME')
      path = path.replace('~', home ?? '')
    }
    const content = await $.fs.read(path)
    const data = JSON.parse(content)
    stateCache = { at: now, data }
    return data
  } catch {
    stateCache = { at: now, data: null }
    return null
  }
}

async function pull($: EngineInterface) {
  const usage = await $.session.usage()
  await update($, snap, prev => ({
    effort: prev?.effort ?? '',
    windows: winsOf(usage.rateLimits),
    ctx: usage.context.percent ?? prev?.ctx ?? null,
  }))
}

export const register: Register = (on, options) => {
  const showModel = options['showModel'] !== false
  const showContext = options['showContext'] === true
  const stateFile = typeof options['stateFile'] === 'string' ? options['stateFile'] : ''
  const oauthUsage = options['oauthUsage'] !== false

  on('session.start', async ($, e, next) => {
    try { await pull($) } catch { /* ignore */ }
    $.clock.every(60_000, () => $.ui.invalidate('ui.render'))
    return next(e)
  })

  on('session.measure', async ($, e, next) => {
    await update($, snap, prev => ({
      effort: prev?.effort ?? '',
      windows: winsOf(e.rateLimits),
      ctx: e.context.percent ?? prev?.ctx ?? null,
    }))
    return next(e)
  })

  on('turn.step', async function* ($, e, next) {
    if (e.agentId === undefined) {
      const effort = e.effort === undefined ? '' : String(e.effort)
      const cur = await read($, snap)
      if (cur !== null && cur.effort !== effort) {
        await update($, snap, () => ({ ...cur, effort }))
      }
    }
    return yield* next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const s = await read($, snap)

    const model = await $.session.model().catch(() => '')

    const now = Date.now()
    const file = stateFile !== '' ? await readStateFile($, stateFile) : null
    const state = mergeState(file, oauthUsage ? await readOauth($) : {}, now)
    const rows = bandRows(s, model, now, showModel, showContext, state)
    if (rows.length === 0) return next(e)

    const { Box, Text } = $.ui.resolve(e)
    const mine = (
      <Box flexDirection="column">
        {rows.map((rowParts, ri) => (
          <Box key={`row-${ri}`} flexDirection="row" flexWrap="wrap">
            {rowParts.map((p, i) => (
              <Text key={`part-${i}`} color={p.color} dimColor={p.dim} weight={p.bold ? 'bold' : undefined}>
                {p.text}
              </Text>
            ))}
          </Box>
        ))}
      </Box>
    )
    const rest = await next(e)
    return (
      <Box flexDirection="column">
        {mine}
        {rest}
      </Box>
    )
  })
}