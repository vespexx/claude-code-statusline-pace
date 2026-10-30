// One rate-limit window as the mod holds it: the share used, when it resets,
// and what the band shows it as (`5h` or `7d`).
export type Win = {
  label: string
  lengthMs: number
  // True for the weekly window: its times show as `Fri-08:52`, the 5h ones as `15:00`.
  day: boolean
  used: number
  resetsAt: number
}

// What the band draws: the last figures the engine reported, taken on a
// measurement, a turn step or the session's start. The model name is read
// from the engine at draw time, not kept here.
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
