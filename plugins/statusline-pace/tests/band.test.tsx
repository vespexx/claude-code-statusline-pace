import { expect, test } from 'claude-code/testing'
import { bandTexts } from '../hooks/register'

test('5h pace 60% shows 60/100', async () => {
  const now = Date.now()
  const resetsAt = now + 3 * 3600_000

  const snap = {
    effort: '',
    windows: [
      { label: '5h', lengthMs: 5 * 3600_000, day: false, used: 0.6, resetsAt },
    ],
    ctx: null,
  }

  const parts = bandTexts(snap, 'gpt-4', now, true, false)
  const text = parts.map(p => p.text).join(' ')
  expect(text).toContain('5h pace 60')
})

test('ETA - when the elapsed share is zero (frac<=0)', async () => {
  const now = Date.now()
  // The reset is further away than the window's full length, so the elapsed
  // share clamps to 0: the ETA is `-`, as in statusline.py when elapsed<=0.
  const resetsAt = now + 6 * 3600_000

  const snap = {
    effort: '',
    windows: [
      { label: '5h', lengthMs: 5 * 3600_000, day: false, used: 0.6, resetsAt },
    ],
    ctx: null,
  }

  const parts = bandTexts(snap, 'gpt-4', now, true, false)
  const text = parts.map(p => p.text).join(' ')
  expect(text).toContain('ETA -/')
})