// One plan window as the mod holds it: which plan it belongs to, the kind the
// band shows it as (`5h`, `7d`, `1mo`), the share used and when it resets.
export type Kind = '5h' | '7d' | '1mo'
export type Win = {
  kind: Kind
  used: number
  resetsAt: number
}

// What the band draws: the last figures the engine or the state file gave,
// taken on a measurement, a turn step or the session's start. The model name
// and the plan are read from the engine at draw time, not kept here.
export type Snap = {
  effort: string
  windows: Win[]
  ctx: number | null
}

declare module 'claude-code' {
  interface PluginState {
    'statusline-pace': { snap: Shaped<Snap | null> }
  }
}