// Shared by tests/test_statusline.py and band.test.tsx. After the `export default` line start the content is plain JSON.
// Time-of-day parts (HH:MM, Www-HH:MM, DD.MM) are replaced by ## and Www so the rows do not depend on the time zone.
export default [
  {
    "name": "claude engine only, head with effort and ctx",
    "now_ms": 1800000000000,
    "engine": [
      {
        "kind": "5h",
        "used": 0.6,
        "reset_ms": 1800007200000
      },
      {
        "kind": "7d",
        "used": 0.4,
        "reset_ms": 1800345600000
      }
    ],
    "state": null,
    "model_id": "claude-opus-5-5",
    "label": "Opus 5.5 (subscription)",
    "effort": "high",
    "ctx": 34.7,
    "showModel": true,
    "showContext": true,
    "rows": [
      "Opus 5.5 (subscription) high ctx 35%",
      "Claude 5h pace 60/60% ETA -/##:## · 7d pace 40/43% ETA -/Www-##:##"
    ]
  },
  {
    "name": "claude engine plus go from state, columns aligned, go current",
    "now_ms": 1800000000000,
    "engine": [
      {
        "kind": "5h",
        "used": 0.3,
        "reset_ms": 1800010800000
      },
      {
        "kind": "7d",
        "used": 0.2,
        "reset_ms": 1800345600000
      }
    ],
    "state": {
      "plans": {
        "go": {
          "7d": {
            "utilization": 0.45,
            "reset": 1800432000
          },
          "1mo": {
            "utilization": 0.73,
            "reset": 1802246400
          }
        }
      }
    },
    "model_id": "glm-5.3-flash-cloud-opencode-go-direct",
    "label": "GLM5.3flash (Cloud, Go Plus, ≈360M out.tok/mo)",
    "effort": "",
    "ctx": null,
    "showModel": true,
    "showContext": false,
    "rows": [
      "GLM5.3flash (Go Plus, ≈360M out.tok/mo)",
      "Claude 5h pace 30/40% ETA -/##:## · 7d pace 20/43% ETA -/Www-##:##",
      "Go                                  7d pace 45/29% ETA Www-##:##/Www-##:## · 1mo pace 73/13% ETA ##.##/##.##"
    ]
  },
  {
    "name": "gemini status-only row aligned under claude",
    "now_ms": 1800000000000,
    "engine": [
      {
        "kind": "5h",
        "used": 0.1,
        "reset_ms": 1800010800000
      }
    ],
    "state": {
      "plans": {
        "gemini": {
          "status": "ok"
        }
      }
    },
    "model_id": "gemini-3-pro",
    "label": "Gemini 3 Pro",
    "effort": "low",
    "ctx": 12,
    "showModel": true,
    "showContext": true,
    "rows": [
      "Gemini 3 Pro low ctx 12%",
      "Claude 5h pace 10/40% ETA -/##:##",
      "Gemini ok"
    ]
  },
  {
    "name": "status after windows and a status-only row",
    "now_ms": 1800000000000,
    "engine": [],
    "state": {
      "plans": {
        "go": {
          "5h": {
            "utilization": 0.14,
            "reset": 1800010800
          },
          "status": "slow 5m"
        },
        "gemini": {
          "status": "quota low"
        }
      }
    },
    "model_id": "x-opencode-go",
    "label": "X (Go)",
    "effort": "",
    "ctx": null,
    "showModel": true,
    "showContext": false,
    "rows": [
      "X (Go)",
      "Go     5h pace 14/40% ETA -/##:## · slow 5m",
      "Gemini quota low"
    ]
  },
  {
    "name": "showModel false hides the head",
    "now_ms": 1800000000000,
    "engine": [
      {
        "kind": "5h",
        "used": 0.3,
        "reset_ms": 1800003600000
      }
    ],
    "state": null,
    "model_id": "claude-opus-5-5",
    "label": "Opus 5.5",
    "effort": "",
    "ctx": 50,
    "showModel": false,
    "showContext": true,
    "rows": [
      "Claude 5h pace 30/80% ETA -/##:##"
    ]
  },
  {
    "name": "no plans, context only gives the head alone",
    "now_ms": 1800000000000,
    "engine": [],
    "state": null,
    "model_id": "gpt-4",
    "label": "gpt-4",
    "effort": "",
    "ctx": 34,
    "showModel": true,
    "showContext": true,
    "rows": [
      "gpt-4 ctx 34%"
    ]
  }
]
