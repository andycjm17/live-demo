# Violation Clip Demo (Mobile)

TikTok LIVE violation notice & AI chatbot prototype — iPhone 17 sized, single-file HTML demo.

## How to run

Open `mobile-demo.html` in any modern browser (Chrome, Safari, Edge, Firefox).

Self-contained — no server, no build step, no dependencies. All videos and thumbnails load via relative paths.

## Files

| File | Purpose |
|------|---------|
| `mobile-demo.html` | The entire demo — HTML + CSS + JS in one file |
| `clip-giftnr.mp4` / `.jpg` | Gift Ban + NR (Body Exposure) clip + first-frame thumbnail |
| `clip-nr.mp4` / `.jpg` | NR (Begging & Solicitation) clip + thumbnail |
| `clip-appeal-approved.mp4` / `.jpg` | "Appeal approved" history video |
| `clip-appeal-rejected.mp4` / `.jpg` | "Appeal not approved" history video |

## App flow

1. **End-stream page** (light theme) — Congratulations screen with stats, rewards, and `⚠️ Restrictions (3)` entry card
2. **Restrictions inbox** — Active (3) / History (3) tabs
3. **Active detail pages** (3 items):
   - Gift Ban + NR (Body Exposure) — standard pattern
   - LIVE visibility restricted **v1 · static** — original pattern (static text description + separate bottom "AI Insight" streaming panel)
   - LIVE visibility restricted **v2 · AI** — new pattern (Restriction Details block IS the AI insight panel with embedded agent-entry buttons; no separate bottom AI panel)
4. **History detail pages** — appeal approved / appeal not approved / appeal in progress
5. **Violation clip player** — full-screen video with `LIVE 12:34:56` timestamp overlay
6. **AI chatbot** — intent-driven conversation (Understand / Improve / Next steps / I think this is wrong)
7. **Appeal modal** — unified reason selection, shared across all entry points (top-right Appeal link and in-chat File an Appeal)

## AI bot architecture

- **Data**: per-violation `POLICY_BODY_EXPOSURE` / `POLICY_BEGGING` / `POLICY_FORMAT_INTERRUPT` — single source of truth (policy text, response templates by intent, mode messages, closures)
- **Mode model**: `chatMode` in {A, B, C, D, E} derived from `(detail.appealable, appealStatus)` — hides dispute/appeal paths in non-appealable states
- **Intent-driven flow**: user picks root intent → AI response → secondary intents or back-to-root → "I'm done" ends anytime
- **Pick-once**: options the user already selected are hidden from subsequent menus (nav options like "I'm done" always shown)
- **Negative options** (e.g. "I think this is wrong") pinned to end of list and lowlighted (gray)
- **Text input**: free-form input at the bottom of chat with keyword-based routing to intent templates
- **Collapsed context**: entering chat auto-collapses the clip preview so messages get more room; tap header to expand; tap video to play full-screen
- **Unified appeal**: in-chat "File a formal appeal" opens the same reason modal as the top-right Appeal link, with chat context pre-filling the suggested reason
- **Speed**: streaming effect is a typewriter animation (6ms/char — 4× faster than initial), not a real LLM

## v1 vs v2 comparison

Click into **LIVE visibility restricted (v1 · static)** vs **(v2 · AI)** to compare:
- v1 = old pattern — factual text + separate AI panel at bottom
- v2 = new pattern — AI drives the Restriction Details block itself, with embedded action buttons

## Not a production system

All responses are hardcoded templates in JS. Streaming is `setTimeout` animation. To wire up a real LLM, replace `streamAIResponse()` with SSE/fetch-stream from a backend proxy and feed the `POLICY_*.understand/dispute/improve/nextSteps` templates as system prompts.
