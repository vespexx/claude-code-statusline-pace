import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, SessionRateLimit } from 'claude-code'

import type { Kind, Snap, Win } from '../types'

// statusline-pace: the subscription pace as a band above the prompt.
// `Opus 5.5 high | 5h pace 60/40% ETA 15:00/16:40 · 7d pace 40/17% ETA Fri-08:52/Tue-08:52 · 1mo pace 73/13% ETA 08.11/29.11`
// pace = used % of the window / elapsed % of the window; ETA = when the limit
// hits 100% at the burn so far / when the window resets. Linear, like the
// plain `statusline.py` in this repo: no history is kept; the figures come
// from the engine, pushed on `session.measure` and pulled at the start.
// Plan-aware (v0.2): shows windows for the plan of the model currently selected
// with /model. Claude plan -> rateLimits (five_hour/seven_day) + state fallback.
// OpenCode Go plan -> state file plans.go (5h/7d/1mo). Other models -> no windows.
// Keep in sync with statusline.py: plan_of, short_label, off_pace, state_windows.

const snap = atom({ plugin: 'statusline-pace', key: 'snap' } as const, null, {
  shape: 'snap-2',
})

const LENGTH: Record<Kind, number> = {
  '5h': 5 * 3600_000,
  '7d': 7 * 86400_000,
  '1mo': 30 * 86400_000,
}

const ENGINE_KINDS: Record<string, Kind> = {
  five_hour: '5h',
  seven_day: '7d',
}

const WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const PLAN_TAGS = new Set(['Go', 'Go Plus', 'subscription', 'free tier'])

const pad = (n: number) => String(n).padStart(2, '0')

// 5h shows `HH:MM`, 7d shows `Ddd-HH:MM` (local), 1mo shows `DD.MM` (1-indexed month).
// Callers guard that `ms` is finite.
export function fmt(kind: Kind, ms: number): string {
  const d = new Date(ms)
  if (kind === '5h') {
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
export function planOf(model: string): 'claude' | 'go' | '' {
  const s = model.toLowerCase()
  const [, items] = labelItems(model)
  const itemSet = new Set(items)
  if (s.includes('opencode-go') || itemSet.has('Go') || itemSet.has('Go Plus')) {
    return 'go'
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

// Mirrors statusline.py state_windows.
export function stateWins(state: unknown, plan: 'go' | 'claude'): Win[] {
  if (typeof state !== 'object' || state === null) return []
  const stateObj = state as Record<string, unknown>
  const plans = stateObj.plans
  const plansObj = (typeof plans === 'object' && plans !== null) ? plans as Record<string, unknown> : {}
  const src = plansObj[plan]
  if (typeof src !== 'object' || src === null) {
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
  const order: Kind[] = ['5h', '7d', '1mo']
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
export function offPace(kind: Kind, util: number, frac: number): boolean {
  if (kind === '5h') {
    return util > Math.max(1.5 * frac, 0.1) || util > 0.75
  }
  return util > frac + 0.05
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

// Build the band parts. Same shape as before but colours from offPace,
// separators ' · ' between windows, ' | ' before first window.
// Never push empty text.
export function bandTexts(
  s: Snap | null,
  model: string,
  now: number,
  showModel: boolean,
  showContext: boolean
): { text: string; color?: string; dim?: boolean }[] {
  const short = shortLabel(model)
  const effort = s?.effort ?? ''
  const head = `${short}${short !== '' && effort !== '' ? ' ' + effort : ''}`

  const wins = s?.windows ?? []
  const winParts = wins.map(w => oneWin(w, now))

  const parts: { text: string; color?: string; dim?: boolean }[] = []
  if (showModel && head !== '' && wins.length > 0) parts.push({ text: head })
  winParts.forEach((part, i) => {
    if (parts.length > 0) parts.push({ text: i === 0 ? ' | ' : ' · ', dim: true })
    parts.push({ text: part.text, color: part.color })
  })
  if (showContext && s && s.ctx !== null) parts.push({ text: ` ctx ${Math.round(s.ctx)}%`, dim: true })
  return parts.filter(p => p.text !== '')
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
    const plan = planOf(model)

    // Build windows for the current plan.
    let windows: Win[] = []
    if (plan === 'claude') {
      windows = s?.windows ?? []
      if (windows.length === 0 && stateFile !== '') {
        const state = await readStateFile($, stateFile)
        windows = stateWins(state, 'claude')
      }
    } else if (plan === 'go') {
      const state = await readStateFile($, stateFile)
      windows = stateWins(state, 'go')
    } else {
      windows = s?.windows ?? []
    }

    const snapForDraw: Snap | null = s === null ? null : {
      effort: s.effort,
      windows,
      ctx: s.ctx,
    }

    // If no windows and no context to show, don't draw.
    // When plan is 'go' but state has no windows yet, don't draw empty band.
    if (snapForDraw === null || (snapForDraw.windows.length === 0 && !showContext)) return next(e)

    const parts = bandTexts(snapForDraw, model, Date.now(), showModel, showContext)
    if (parts.length === 0) return next(e)

    const { Box, Text } = $.ui.resolve(e)
    const mine = (
      <Box flexDirection="row" flexWrap="wrap">
        {parts.map((p, i) => (
          <Text key={`part-${i}`} color={p.color} dimColor={p.dim}>
            {p.text}
          </Text>
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