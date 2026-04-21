# Opening framework · How to open a presentation of AI Insight

**Purpose · 目的** — A scripted 5–7 minute opening you can use as the first frame when
presenting AI Insight to stakeholders, reviewers, or cross-functional partners.
Covers the problem, the hypothesis, and the three layers of the system
(frontend / backend / algorithm) without going deep on any single one.

> **中文一句话:** 把这个功能介绍给别人的开场框架——5-7 分钟以内讲清"我们在做什么 / 为什么这么做 / 前端后端算法各自在做什么"。

---

## Structure at a glance

| # | Segment | Time | What it does |
|---|---|---|---|
| 1 | Problem hook | 30 s | "Here's what's broken today." |
| 2 | Hypothesis | 30 s | "Here's what we think fixes it — but it's a bet." |
| 3 | The system · three layers | 2 min | Frontend / backend / algorithm, each in one paragraph. |
| 4 | Architectural novelties | 1.5 min | The three things worth asking about in Q&A. |
| 5 | Demo walk-through flags | 2 min | 3 archetype click-throughs. |
| 6 | What's next | 30 s | Phase 2 / 3 preview. |

---

## Segment 1 · Problem hook (30 s)

> TikTok LIVE's machine moderation today runs at roughly **80 % precision, 60 %
> recall, and 10 % over-enforcement**. That means for every 100 creators who get
> flagged, around **20 may be misjudged** — either false positives, context
> failures, or edge cases. Layer on the fact that our current education channel
> for a flagged creator is a static FAQ link, and you get three outcomes we see in
> the data: **high appeal rate, frustrated creators, persistent repeat
> violations**. The appeals clog review queues, the frustration shows up in
> social sentiment, and the repeat violations mean the education isn't actually
> landing.

> **中文浓缩:** 机审 80% 精度 / 60% 召回 / 10% 过罚 → 20% 用户可能被冤枉；目前教育只有静态 FAQ 链接 → 申诉率高、用户焦虑、重复违规。

---

## Segment 2 · Hypothesis (30 s)

> We think creators want to **understand** before they **appeal**. If we can
> give them contextual AI education at the exact moment they see the flag —
> grounded in the real policy, tuned to their tier and history — we expect to
> see fewer irrational appeals and better long-term compliance. But I want to
> be precise: this is **a hypothesis, not an assumption**. The whole MVP is
> chartered as a Discovery Project — success is a clean learning signal in
> either direction.

> **中文:** 核心假设 — "创作者想先理解再申诉"。Demo 是 Discovery Project，成功定义是能给出方向清晰的验证结果，不是一定要指标达成。

---

## Segment 3 · The system · three layers (2 min)

Walk through one paragraph per layer. Tempo: ~40 seconds each.

### Frontend (creator-facing · what they see)

> Per-violation AI Insight page — every single flag gets its own dedicated page
> with a short opener, four visually-equal intents (*Why was it flagged? / How
> do I avoid this? / What happens now? / I have a different view*), and a
> persistent chat history scoped by the creator + live-session + violation
> type. We ship a three-tier feedback loop — thumbs-up on each message, a
> "did the chat help?" sheet at session close, and behavioural signals
> downstream. Premium G8+ creators unlock a human-agent channel. Cross-violation
> continuity is built in: if you flagged twice in one LIVE, the second opener
> already knows you discussed the first.

### Backend (platform · what stores and routes it)

> Three data flows — **event pipeline** (session opens, intents picked, messages
> sent, feedback logged, killswitch toggled, evidence submitted); **AI session
> aggregation** keyed by `(live_session_id, violation_type)` so the LLM sees
> sibling violations' context even though the UX shows each flag on its own
> page; **editable RAG-grounded templates** so ops can hot-edit the proactive
> openers from a dashboard without shipping code. Layer-8 operations fallback
> + a 30-second-SLA emergency kill switch catch the 5 % residual risk the
> engineering guardrails don't.

### Algorithm (AI · what actually generates the answer)

> Three-call pipeline: **(1) input normalisation + intent classification**
> (small model, also our prompt-injection defence), **(2) RAG retrieval + Rerank
> LLM** against Creator Academy and Policy Library, **(3) grounded generation**
> with a 140-character hard ceiling and temperature 0. Seven guardrail layers —
> input sanitisation, attack-intent classifier, meta-prompt sandwich, RAG
> grounding, Chain-of-Verification, citation hard-match, output compliance
> classifier — plus the operations fallback. Target: **95 % engineering
> coverage + 5 % ops coverage.**

> **中文总结:** 前端看着是"违规+AI 聊天"；后端是"事件流 + AI session 聚合 + 可热改的模板"；算法是"3 次 LLM 调用 + 7 层护栏 + 运营兜底"。三层协作。

---

## Segment 4 · Architectural novelties (1.5 min)

Three things worth surfacing because they're the *original* design contributions
— not just "AI chat for moderation", which is table stakes:

1. **Three-tier feedback loop** — message (Layer 1), session (Layer 2),
   behavior (Layer 3). Each tier is independently signal-generating, and
   together they cross-validate four failure modes instead of one. Task 1.2
   adds a smart step: **Layer 2 auto-derives from Layer 1** when the signal
   is decisive (≥75 % same-direction ≥3 votes), cutting the survey-fatigue
   tax on engaged users.
2. **Two-layer structure** — UX-independent violation pages paired with
   AI-aggregated sessions. Creator sees three separate violation pages; LLM
   sees one conversation. Strategy β: "separate display, shared context."
3. **Discovery Project framing** — success = a clean learning signal in
   either direction. If the hypothesis fails, we learn and pivot. If it
   succeeds, we invest. Avoids the anti-pattern of "launch then measure
   whether the number went up."

> **中文简版:** 三个原创亮点 — 三层反馈 / 两层结构 / Discovery Project 定位。

---

## Segment 5 · Demo walk-through flags (2 min)

Live walk-through using the Render-deployed URL:

1. **Login screen** — 5 archetype cards.
2. **Rookie Sarah** → end-stream → Restrictions → tap V2 → watch the
   **rookie-toned opener** stream at 25 ms/char, pick an intent, give a 👍.
3. Back → tap V3 → opener now references V2 context
   ("This is your 2nd … earlier we walked through …") — **that's the §2.2
   aggregation**.
4. Switch account → **Repeat-flagger Mike** → same violation page now shows
   an orange *"5th flag in 30d · pattern detected"* banner. Different tone
   in the opener.
5. Switch → **VIP Zoe · G10** → pink "priority support" banner in every
   screen; chat top-bar shows `G10 ⭐`; human-agent queue modal shows
   *position #1 / ETA 1 min* (tier boost).
6. Dashboard tab → live event stream fills up in real time → AI Session
   Inspector shows the V2+V3 context blob explicitly → Templates editor lets
   you edit the proactive opener copy live.
7. Kill switch → back to mobile → yellow "AI Insight paused by operations"
   banner appears in chat.

> **中文脚本:** 登录页 → Rookie Sarah → Repeat Mike → VIP Zoe → 切到 dashboard → kill switch → 回 mobile 看降级状态。每一步都演 PRD 一个章节。

---

## Segment 6 · What's next (30 s)

> Phase 2 (Q3-Q4 2026) extends single-LIVE → cross-LIVE, lands Layer-5 and
> Layer-7 guardrails (closing the 5 % gap to ~99 % safety coverage), and
> ships a moderator-side AI summarisation tool. Phase 3 (2027+) moves reactive
> to proactive: multimodal LLMs reading clip frames directly, cross-violation
> pattern detection, and pre-LIVE risk reminders. This MVP generates the data
> that trains Phase 2's classifiers.

> **中文:** Phase 2 跨直播 + 补 Layer 5/7 + 审核员工具；Phase 3 多模态 + 开播前提醒。MVP 产生的数据就是 Phase 2 的训练集。

---

## Segment 7 (optional) · The question people usually ask

> *"What happens when the AI says something the reviewer later disagrees with?"*

The demo's **Track C** restriction-agreement feedback, plus the evidence-submission
channel (task 1.4), are our answer. The AI **never** says "you were right, the
system was wrong." It only rates whether evidence is *substantive*, and below a
confidence threshold (default 0.85) it just logs the context for the human
reviewer. The dashboard tracks an **AI ↔ reviewer agreement rate**; if it drops
below 75 %, we tune the threshold up. This explicitly keeps the AI from
contradicting the final arbitrator.

> **中文 FAQ:** AI 不会说"你对 / 系统错了"——只会评估证据是否 substantive。低置信度下只是把上下文存下来给审核员参考，不做定性。我们监控 AI ↔ 审核员 agreement rate，掉到 75% 以下就调高阈值。
