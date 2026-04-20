# TikTok LIVE · AI Insight Demo (Mobile)

Self-contained mobile prototype of the AI Insight violation-education flow described in the [TikTok LIVE AI Insight PRD](TikTok_LIVE_AI_Insight_PRD.docx). Single-file HTML, no build step, sized for iPhone 17 (402 × 874).

## How to run

Open `mobile-demo.html` in any modern browser (Chrome, Safari, Edge, Firefox). Videos and thumbnails load via relative paths — keep the `clip-*.mp4` / `clip-*.jpg` files alongside it.

## Files

| File | Purpose |
|------|---------|
| `mobile-demo.html` | Entire demo — HTML + CSS + JS in one file |
| `clip-nr.mp4` / `.jpg` | Inorganic Gift Solicitation clip + first-frame thumb |
| `clip-appeal-approved.mp4` / `.jpg` | History · Appeal approved video |
| `clip-appeal-rejected.mp4` / `.jpg` | History · Appeal not approved video |
| `clip-giftnr.mp4` / `.jpg` | History · Sexually-suggestive (no AI insight) video |

## App flow

1. **End-stream page** (light theme) — Congratulations screen, ⚠️ Restrictions (1) entry card.
2. **Restrictions inbox** — Active (1) / History (3) tabs.
3. **Active detail page** — single AI Insight pattern:
   - Restriction header + status
   - Plain-text Restriction details (offline, factual)
   - Violation clip (tap to play)
   - **AI Insight panel** — typewriter opening message (25 ms/char) + 4 equal-weight intent options (`💡 Why was my LIVE flagged?` · `📚 How do I avoid this?` · `⏱️ What happens now?` · `🤔 I have a different view`)
4. **History detail pages**:
   - *Appeal approved* — no AI insight (educational value already delivered by the favourable outcome)
   - *Appeal not approved* — AI Insight chat area with educational opener + intents (no dispute path)
   - *Appeal in progress* — AI Insight chat area in learning-only mode (3 intents, dispute hidden while review pending)
5. **AI chat** — picking an intent on the Violation Page deep-links into the chat with that intent already selected.
6. **Appeal modal** — unified reason selection, shared by the top-right Appeal link and in-chat "File a formal appeal".

## PRD UX patterns wired in

| PRD ref | Behaviour |
|---------|-----------|
| §2.1 Scenario 2 | 4 visually-equal intents — no dark-pattern lowlight; pick-once (selected option disappears) |
| §2.1 Scenario 3 | Typewriter at 25 ms/char; per-message Layer-1 👍/👎 fades in once typing completes |
| §3.5 Layer 1 | Message-level feedback toggles + counts logged |
| §2.1 Scenario 4 | Layer-2 session feedback bottom sheet — appears on close when chat had ≥2 turns and Layer-1 has <3 same-direction votes |
| §2.1 Scenario 5 | Top-right Appeal link **and** in-chat "File a formal appeal" funnel into the same option-pick modal; AI never drafts the user's appeal text |
| §3.4 Persistent | Each violation has its own conversation surface; opening AI Insight from the Violation Page or appeal-result page reuses the same intent flow |

## "LLM" (preset interaction)

All responses are hardcoded templates in `POLICY_BEGGING` / `POLICY_BODY_EXPOSURE`. The typewriter is `setTimeout` animation — no LLM calls. The 140-char (CN) limit is enforced client-side via `clampToCharLimit`. To wire up a real model, swap the `appendAIMessage` typewriter for SSE/fetch-stream with the same templates as system prompts.

## Not a production system

UX-only prototype for design review and stakeholder walk-throughs. Real backend, RAG retrieval, attack-classifier, citation hard-match etc. live in the §3 architecture chapter of the PRD.
