# Phase summaries · 1 · 2 · 3

**Purpose · 目的** — A one-paragraph summary plus 2–3 key features per phase,
designed to be lifted directly into a deck or exec brief.

> **中文:** 每个 Phase 一段 150 字左右的产品总结 + 2-3 个关键能力点，可以直接贴进 slide 或 exec brief。

---

## Phase 1 · MVP · Discovery launch

> **AI Insight MVP validates the core hypothesis that creators want to
> *understand* — not just appeal — moderation decisions.** The launch features
> per-violation AI chat entries with 25 ms/char typewriter openers, four
> equal-weight intents (*Understand / Improve / Next steps / I have a different
> view*), and a persistent conversation model scoped by
> `(user, live_session, violation_type)`. The three-tier feedback loop —
> message-level 👍/👎 (Layer 1), session-level "did it help?" (Layer 2, with
> auto-derivation from strong Layer-1 signals), and behavioural signals like
> appeal rate and 7-14-day repeat violation (Layer 3) — cross-validates four
> failure modes. A RAG + LLM pipeline grounded in Community Guidelines and
> Creator Academy generates responses with a 140-character hard ceiling. Seven
> engineering guardrail layers plus 1 %-daily audit + 30-second-SLA kill switch
> achieve 95 % + 5 % safety coverage. G8+ premium creators unlock a human-agent
> channel with priority queuing. A restriction-agreement feedback surface
> (separate from chat-quality feedback) and a high-threshold evidence-submission
> channel close the "AI vs reviewer conflict" risk. Chartered as a Discovery
> Project — success is clean directional learning signals, not metric targets.

**Key features · 关键能力:**
1. **Per-violation AI page + 4-intent chat** (PRD §2.1) — violation page is the
   AI Insight entry; 4 equal-weight intents with pick-once 200 ms fade;
   persistent conversation restores instantly on re-entry.
2. **3-tier feedback loop** (PRD §3.5) — message / session / behaviour.
   Layer 2 auto-derives from decisive Layer-1 signal to cut survey fatigue
   (task 1.2). A separate "restriction agreement" surface (task 1.1)
   disambiguates "did the AI help?" from "do you agree with enforcement?"
3. **G8+ premium human-agent channel + evidence submission** — premium
   creators get priority human routing; all creators can attach context/evidence
   for a 2nd-look with a high AI confidence threshold (default 0.85) so AI
   never overturns a future reviewer's decision.

> **中文总结 · Phase 1 三个关键能力:** (1) 每条违规独立 AI Insight 页 + 4
> 平权 intent；(2) 三层反馈 + Layer 2 自动推导（强信号跳过询问）；(3) G8+
> 人工坐席通道 + 高阈值证据提交。

---

## Phase 2 · Q3-Q4 2026 · Cross-LIVE + close safety gaps

> **Phase 2 extends AI Insight from single-LIVE to cross-LIVE, and closes the
> remaining 5 % safety gap.** A new `conversation_continuity_key = (user_id,
> violation_type)` binds same-type violations across sessions — when a creator
> hits a familiar policy on a new LIVE, the AI already knows the prior
> conversation. Real SSE streaming replaces the 25 ms/char fake typewriter,
> matching the rhythm of the live model. Layer-5 Chain-of-Verification and
> Layer-7 output compliance classifier land, pushing engineering coverage above
> 99 % and reducing reliance on the ops fallback. History becomes queryable
> across `live_sessions` (creators can search "why did my LIVE on 4/13 get
> flagged?"). A moderator-side AI summarisation tool lands inside the mod
> console — reviewers see *"this creator discussed intent = understand N times,
> 👍 Y %, 👎 Z %"* at decision time, making review faster and more informed.
> Intent granularity expands: tier-2 sub-intents (Why / Rule / Impact) become
> first-class choices under Understand, surfacing the already-built
> `showSecondaryIntents` logic.

**Key features · 关键能力:**
1. **Cross-LIVE aggregation** — `conversation_continuity_key` ties same-type
   violations across sessions; opener references prior LIVEs' intents; the
   AI Session Inspector gains a cross-LIVE tab.
2. **Layer-5 + Layer-7 guardrails complete** — CoV self-check on every
   generated reply; compliance classifier on output. Coverage hits ~99 %;
   the 1 %-daily audit quota drops.
3. **Moderator-side AI summarisation tool** — inline in the existing mod
   console. Reviewers see the creator's chat history + tier + archetype +
   past appeal outcomes in a single glance, typically at decision time.

> **中文 · Phase 2 三个关键能力:** (1) 跨直播聚合（同用户同类型连续上下文）；
> (2) Layer 5 + 7 护栏补齐（99%+ 工程覆盖）；(3) 审核员侧 AI 摘要工具。

---

## Phase 3 · 2027+ · Reactive → proactive

> **Phase 3 moves AI Insight from reactive to proactive — from "explain
> decisions" to "prevent violations".** Multimodal LLMs natively understand
> clip frames, replacing the text-only proxies we use for visual violations
> today — this collapses entire categories of explanation gaps (body-exposure,
> framing, props). Cross-violation reasoning unlocks deep pattern detection,
> not just aggregation: *"3 similar flags in 30 days across 2 LIVEs — the
> common thread is camera angle at 45° + torso framing; here's the one change
> that would fix all three."* Proactive intervention pipes chat history and
> behaviour signals into a risk-scoring model; high-risk creators receive
> pre-LIVE reminders *before* they violate, customised by their own history.
> Formal system lifecycle management establishes Kill / Upgrade / Sunset
> criteria — so the product can be cleanly retired or upgraded without orphan
> data or abandoned creators. The product identity shifts: AI Insight is no
> longer the reviewer's hand-off; it's the platform's teacher.

**Key features · 关键能力:**
1. **Multimodal LLM (native clip understanding)** — multimodal Sonnet or
   successor reads clip frames directly; resolves "擦边" / body-exposure /
   framing-nuance explanation gaps that text descriptions can't.
2. **Pre-LIVE proactive risk reminders** — based on Phase 1+2 signals, the
   top risk-scored creators get contextual reminders immediately before going
   live ("you had 3 IGS flags last month — here's the specific framing to
   watch"). Distinct from post-violation education.
3. **System lifecycle governance** — formal Kill / Upgrade / Sunset criteria,
   data migration flows, creator notification cadence. Resolves R-015.

> **中文 · Phase 3 三个关键能力:** (1) 多模态 LLM 原生看视频帧；
> (2) 开播前风险提醒（主动干预）；(3) 系统生命周期治理（Kill/Upgrade/Sunset 规范化）。
