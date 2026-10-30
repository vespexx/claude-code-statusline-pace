import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, SessionRateLimit } from 'claude-code'

import type { Snap, Win } from '../types'

// statusline-pace: the subscription pace as a band above the prompt.
// `Opus high | 5h pace 60/40% ETA 15:00/16:40 · 7d pace 40/17% ETA Fri-08:52/Tue-08:52`
// pace = used % of the window / elapsed % of the window; ETA = when the limit
// hits 100% at the burn so far / when the window resets. Linear, like the
// plain `statusline.py` in this repo: no history is kept; the figures come
// from the engine, pushed on `session.measure` and pulled at the start.

const snap = atom({ plugin: 'statusline-pace', key: 'snap' } as const, null, {
  shape: 'snap-1',
})

// The subscription windows the band knows, by the kind the engine reports.
// Unknown kinds (a gateway's spend limit) have no known length: left out.
const KINDS: Record<string, { label: string; lengthMs: number; day: boolean }> = {
  five_hour: { label: '5h', lengthMs: 5 * 3600_000, day: false },
  seven_day: { label: '7d', lengthMs: 7 * 86400_000, day: true },
}

const WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const pad = (n: number) => String(n).padStart(2, '0')

// 5h shows `15:00`, 7d shows `Fri-08:52`; local time, like the terminal's clock.
const fmt = (day: boolean, ms: number): string => {
  const d = new Date(ms)
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  return day ? `${WEEK[d.getDay()]}-${hm}` : hm
}

const winsOf = (rows: readonly SessionRateLimit[]): Win[] => {
  const wins: Win[] = []
  for (const row of rows) {
    const kind = KINDS[row.kind]
    if (kind === undefined || row.resetsAt === undefined) continue
    const resetsAt = Date.parse(row.resetsAt)
    if (!Number.isFinite(resetsAt)) continue
    wins.push({ label: kind.label, lengthMs: kind.lengthMs, day: kind.day, used: Math.max(0, row.percentUsed) / 100, resetsAt })
  }
  return wins
}

async function pull($: EngineInterface) {
  const usage = await $.session.usage()
  await update($, snap, prev => ({
    effort: prev?.effort ?? '',
    windows: winsOf(usage.rateLimits),
    ctx: usage.context.percent ?? prev?.ctx ?? null,
  }))
}

// The one-window part of the band: `used` at the burn so far reaches 100%
// now (`now`), never before the reset (`-`), else at that time.
function oneWin(win: Win, now: number) {
  const left = win.resetsAt - now
  const stale = left <= 0
  const util = stale ? 0 : win.used
  const frac = stale ? 0 : Math.min(1, Math.max(0, 1 - left / win.lengthMs))
  const out =
    util >= 1 ? 'now' : util <= 0 || frac <= 0 ? '-' : fmt(win.day, now + ((1 - util) / util) * frac * win.lengthMs)
  const color = out === '-' ? 'success' : util >= 1 ? 'error' : 'warning'
  const usedPct = Math.floor(util * 100 + 1e-9)
  const text = `${win.label} pace ${usedPct}/${Math.round(frac * 100)}% ETA ${out}/${stale ? 'now' : fmt(win.day, win.resetsAt)}`
  return { text, color }
}

// The band's runs, in draw order: the model head, then each window part,
// joined by ` | ` before the first window and ` · ` between windows.
export function bandTexts(s: Snap, model: string, now: number, showModel: boolean, showContext: boolean) {
  const head = `${model}${model !== '' && s.effort !== '' ? ' ' + s.effort : ''}`
  const wins = s.windows.map(w => oneWin(w, now))
  const parts: { text: string; color?: string; dim?: boolean }[] = []
  if (showModel && head !== '') parts.push({ text: head })
  wins.forEach((part, i) => {
    if (parts.length > 0) parts.push({ text: i === 0 ? ' | ' : ' · ', dim: true })
    parts.push({ text: part.text, color: part.color })
  })
  if (showContext && s.ctx !== null) parts.push({ text: ` ctx ${Math.round(s.ctx)}%`, dim: true })
  return parts
}

export const register: Register = (on, options) => {
  const showModel = options['showModel'] !== false
  const showContext = options['showContext'] === true

  on('session.start', async ($, e, next) => {
    try { await pull($) } catch { /* ignore */ }
    // The band's elapsed share moves even when no window does: ask for a
    // redraw once a minute so the times stay current while the session is idle.
    $.clock.every(60_000, () => $.ui.invalidate('ui.render'))
    return next(e)
  })

  // The figures, pushed: every point a window moves, every turn.
  on('session.measure', async ($, e, next) => {
    await update($, snap, prev => ({
      effort: prev?.effort ?? '',
      windows: winsOf(e.rateLimits),
      ctx: e.context.percent ?? prev?.ctx ?? null,
    }))
    return next(e)
  })

  // The effort as the engine resolved it for the request it sends now (the
  // same one the status-line input carries); main loop only. A streaming
  // event: the hook is an async generator and forwards the stream.
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
    // No pace data yet (before the first response of a subscription session,
    // or off a subscription): stay silent rather than draw a model line alone.
    if (s === null || (s.windows.length === 0 && s.ctx === null)) return next(e)

    const model = await $.session.model().catch(() => '')
    const parts = bandTexts(s, model, Date.now(), showModel, showContext)
    if (parts.length === 0) return next(e)

    const { Box, Text } = $.ui.resolve(e)
    return (
      <Box>
        {parts.map((p, i) => (
          <Text key={`part-${i}`} color={p.color} dimColor={p.dim}>
            {p.text}
          </Text>
        ))}
      </Box>
    )
  })
}