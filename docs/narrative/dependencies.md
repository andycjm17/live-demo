# Prerequisite dependency map · cross-team · Phase 1 · 2 · 3

**Purpose · 目的** — Ship-blocker dependencies across Legal / DA / Ops / Infra / Algo
/ UX Writing, organised by phase, with a text-form Gantt sketch at the bottom.

> **中文一句话:** 每个 phase 的前置依赖和跨团队协作点，按职能分列，附 Gantt 文本示意。

---

## Phase 1 · MVP launch blockers

Drawn from PRD Appendix A · Risk Register.

| Owner | Dependency | PRD Ref | Status in demo |
|---|---|---|---|
| **Legal** | R-001 · sign-off on 5 % residual AI output risk + operations fallback design | §4.4, §3.3 L8 | ⏳ manager must broker |
| **Manager** | R-010 · MVP scope confirmation (optimistic 3.5 mo / pessimistic 7 mo) | §1 Expected delivery | ⏳ pending |
| **Policy / 策略同事** | R-011 · primary violation type selection (recommend IGS · 挂外链) | Appendix A | 🟡 demo uses IGS + body_exposure — final pick pending |
| **DA** | R-005 · appeal-success-rate guardrail design + A/B sample size | §5 | ⏳ |
| **Ops / 运营** | R-003 · 3–5 new reviewers for 1 % daily audit (~1000 items/day) | §3.3 L8 | ⏳ staffing |
| **Infra / 直播基础设施** | R-012 · clip pass-through service (LIVE stream → AI Insight backend) | §1 | ✅ demo mocks this; prod must build real |
| **Algo** | R-014 · cross-turn hallucination solution (history summarisation + citation verification) | §3.3 L4/6 | 🟡 demo uses Claude direct; prod needs stricter grounding |
| **UX Writing** | Final intent + feedback copy + Starling keys (EN/中) | §2.3 | ✅ draft in demo; Starling keys pending |

> **中文:** 这是上线前必须关掉的 8 个依赖，大多需要 Legal / Manager / Ops 主导。
> 工程侧 demo 基本都跑通了，缺的都是"人的工作"。

---

## Phase 2 · Q3-Q4 2026 prerequisites

Phase 2 assumes Phase 1 is live with 6 weeks of data.

| Owner | Dependency | Notes |
|---|---|---|
| Product | Phase 1 learning review clean (PRD §9.4) — Go / No-Go decision made per §9.3 decision map | Gate to Phase 2 |
| Infra | `ai_session` storage schema extension for `conversation_continuity_key = (user_id, violation_type)` | Keeps cross-LIVE context |
| Infra | True SSE streaming from internal LLM service | Replaces 25 ms/char fake typewriter |
| Algo | Layer-5 CoV classifier training data — sourced from Phase 1 Layer-1 👍/👎 labels | Need ~10 k labeled pairs minimum |
| Algo | Layer-7 output compliance classifier — model + training pipeline | Can share infra with CoV |
| Infra + Moderation | Mod-console API access for AI summarisation tool integration | Mod tool team must open an API |
| Legal | Data retention policy finalised (§4.2) — 90 d default, deletion cascade, PII desensitisation | Required before Phase 2 cross-LIVE store |
| DA | New metric definitions for cross-LIVE aggregation effectiveness | Continuity uplift measurement |

---

## Phase 3 · 2027+ prerequisites

Phase 3 is bet-the-architecture — proactive + multimodal.

| Owner | Dependency | Notes |
|---|---|---|
| Product | Phase 2 launched + learning review clean | Gate to Phase 3 |
| Infra + Algo | Multimodal model budget allocation (significantly more per call) | Size TBD by model choice at 2027 |
| Algo | Cross-violation pattern detection infrastructure (graph-based pattern finder, not just aggregation) | Builds on Phase 2 `conversation_continuity_key` |
| Infra | Pre-LIVE push notification pipeline — distinct from Phase 1 post-LIVE deep-link infra | New channel |
| Algo | Creator risk-scoring model — trained on Phase 1 + Phase 2 aggregated signals | Validates Phase 2's signal hoarding |
| Legal | Sign-off for proactive-intervention UX (R-015 extension) | Pre-LIVE push = different consent story |
| Ops | Scale-up to 10+ reviewers with AI-assist tooling | Phase 2 tool enables this |

---

## Cross-team timeline · text Gantt

Each ▒ block ≈ 1 month of dedicated effort for that team.

```
                     Phase 1 (MVP)       Phase 2 (cross-LIVE)   Phase 3 (proactive)
                     (~3.5–7 mo)         (Q3–Q4 2026)           (2027+)
                     ───────────────     ────────────────────   ───────────────────
Legal                ▒▒▒                 ▒                       ▒▒
DA                   ▒▒▒                 ▒▒                      ▒▒
Ops / 运营           ▒▒                  ▒▒▒                     ▒▒▒▒
Infra                ▒▒▒▒                ▒▒▒                     ▒▒▒▒
Algo                 ▒▒▒                 ▒▒▒▒                    ▒▒▒▒▒
UX Writing / L10n    ▒▒                  ▒                       ▒
Product (PM)         ▒▒▒▒▒               ▒▒▒                     ▒▒▒
```

> **中文解读:** Algo 在 Phase 2-3 是工作量重心；Ops 是持续扩编的节奏（与 audit
> 覆盖率耦合）；Legal 在每个 phase 都要介入（risk 签字）；UX Writing 主要集中在 Phase 1。

---

## Critical-path dependencies (ship-blockers across phases)

The four items that genuinely gate the next phase if they slip:

1. **Legal R-001 sign-off** — blocks Phase 1 launch. No amount of engineering
   polish bypasses this.
2. **R-012 clip pass-through service** — Phase 1 can't generate real AI
   responses without real clip metadata.
3. **`conversation_continuity_key` schema extension** — blocks Phase 2. The
   whole Phase 2 value proposition collapses without this.
4. **Multimodal model budget allocation** — blocks Phase 3. Without native
   clip understanding, Phase 3 is a re-branding of Phase 2.

> **中文关键路径:** Legal 签字 / Clip 透传 / 跨直播 schema / 多模态模型预算 — 这四件事任何一件掉，下一个 phase 就动不了。

---

## Inconsistencies in the source PRD · flagged for manager

1. **R-015 system lifecycle** is listed as a Phase 2 owner in Appendix A but
   as Phase 3 work in §D Future Work.
   → **Recommend splitting:** Phase 2 writes the kill / sunset **trigger
   criteria** (operational need, builds on the 30-s kill switch already in
   place); Phase 3 builds the full upgrade / sunset **governance + data
   migration**.

2. **Canary-token prompt-injection defence** is listed in §1 out-of-scope but
   not explicitly phased.
   → **Recommend** bundling with Layer-5 / Layer-7 in Phase 2.

> **中文:** PRD 自身有两处 Phase 归属不一致，建议在 Phase 2 planning 同步修订。
