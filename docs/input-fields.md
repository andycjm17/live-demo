# Input field schema · 5-bucket matrix

**Purpose · 目的** — An inventory of every piece of structured input the AI Insight
system reads or writes, grouped into five domain buckets (creator / live / violation
/ punishment / appeal), plus a per-feature mapping so downstream engineering can see
exactly which bucket each feature needs.

> **一句话中文说明:** 把 AI Insight 所需的所有输入字段按"用户 / 直播间 / 违规 / 处罚 / 申诉"五大类盘点，再按功能列一张需求矩阵，让后端工程可以精确对齐 schema。

---

## Section 1 · Field catalogue

Columns:
- **Today (wired)** — fields currently passed through beacons, rendered in the demo,
  or stored in `aiinsight.db`.
- **Potential additions** — fields referenced in the PRD or common in ops tooling,
  not yet plumbed. Candidates for Phase 2 / 3.

### 1.1 · 用户标签 · Creator signals

| Today (wired) | Potential additions |
|---|---|
| `user_id`, `user_name`, `user_level` (G1–G11), `archetype`, `priorViolations`, `appealHistory`, `followers`, `totalLives` | `register_date`, `KYC status`, `content_category`, `region`, `language`, `monetization_tier`, `historical_compliance_score` (0-100 rolling), `recent_activity_intensity` (hours LIVE last 7d), `audience_demographics` (age/region buckets), `previous_strike_count`, `community_ambassador_flag` |

> **中文:** 创作者身份信号。当前已联通的 8 个字段已足以支撑 5 个 archetype 的 demo
> 行为分叉；Phase 2 要加 `content_category`（视频题材）和
> `historical_compliance_score`（滚动合规分）支撑跨直播风险识别。

### 1.2 · 直播间标签 · Live-session signals

| Today (wired) | Potential additions |
|---|---|
| `live_session_id`, `name`, `startedAt`, `durationLabel` | `start_region`, `peak_viewers`, `gift_revenue_this_session`, `content_theme`, `co_host_ids`, `scheduled_vs_impromptu`, `device_type` (iOS/Android/model), `network_quality`, `language` (distinct from user lang), `hashtags_used`, `replay_available`, `avg_chat_rate`, `gift_sender_count` |

> **中文:** 单场直播的元数据。`live_session_id` 已是聚合层的主键，但 PRD §2.2 的
> 更深聚合（如 "这场直播前 20 分钟 peak 观众数"）还没接入。Phase 2 里加 `peak_viewers`
> 和 `gift_revenue_this_session` 可以让 AI 在对话里指出经济动机。

### 1.3 · 违规信息 · Violation signals

| Today (wired) | Potential additions |
|---|---|
| `violation_id`, `violation_type`, `video_ts`, `policy_id`, clip refs (`videoSrc`, `videoThumb`) | `model_id`, `model_version`, `confidence_score`, `multi_modal_signals` (visual/audio/OCR per modality scores), `severity_tier` (P0–P5), `repeat_pattern_flag` (k-th), `human_pre_review_flag`, `cross_policy_references`, `content_language`, `detected_entities` (props / text OCR) |

> **中文:** 违规事件本身。当前只传违规类型和时间戳；Phase 2 的 Layer-5
> Chain-of-Verification 需要 `confidence_score` 和 `multi_modal_signals` 做事实核验，
> 否则 AI 在对话里只能说 "the system detected"，没法具体。

### 1.4 · 处罚信息 · Punishment signals

| Today (wired) | Potential additions |
|---|---|
| `impact` (text label), `statusTitle`, `statusDate` (range), `appealable`, restriction type | `duration_hours`, `auto_lift_vs_manual`, `downstream_impacts` (recommendation freeze / monetization pause / visibility reduction — each quantified), `escalation_tier` (soft / firm / strike), `appeal_window_hours`, `grace_period_hours`, `probation_status`, `currently_live_blocked` |

> **中文:** 处罚范围和期限。当前 `impact` 是一行文案，Phase 2 需要结构化
> `downstream_impacts` 以便 AI 在"What happens now?" 的回答里精确说出"推荐冻结 7 天，礼物不影响"。

### 1.5 · 申诉信息 · Appeal signals

| Today (wired) | Potential additions |
|---|---|
| `appealReason` (option-based), `appealResult.status`, aggregate `appealHistory` on user | `submission_ts`, `evidence_attached` (bool + clip/text refs), `reviewer_id`, `reviewer_tier`, `review_duration_ms`, `decision_reason`, `reviewer_notes` (internal only), `second_appeal_path_available`, `successful_appeal_impact` (rewards repaid / reach restored / visibility restored) |

> **中文:** 申诉流程数据。`evidence_attached` 是 task 1.4 刚加进来的新字段，走
> `/api/evidence/submit`；其他如 `reviewer_id` 和 `review_duration_ms` 是
> Phase 2 的 moderator-side AI tool 的前置依赖。

---

## Section 2 · Function → bucket requirement matrix

Which buckets does each frontend / backend feature need? `●` = required, `○` = uses if available.

| Feature | Creator | Live | Violation | Punishment | Appeal |
|---|:---:|:---:|:---:|:---:|:---:|
| Chat opener (`getOpening` in mobile-demo.html) | ● name, archetype, level, priorViolations | — | ● type, timestamp, policyDescShort | ○ impact | ○ appealHistory (appealer) |
| Claude LLM reply (`/api/chat/complete`) | ● + engagement | ○ duration, context | ● + `policyDescLong`, detection signals | ○ restrictions text | ○ prior appeal outcomes |
| Push notification (PRD §2.1 Scenario 1) | ● `user_id`, notification prefs | ● `session_id` (grouping) | ● `violation_id`, `type`, headline | ● one-liner impact | — |
| Violation detail page | ● all displayed fields | ● all | ● all | ● all | ○ appeal state if exists |
| AI Insight proactive opener (typewriter) | ○ archetype | — | ● type, timestamp, headline | ● impact | ○ status |
| Appeal modal pre-fill | ● past appeal reasons pattern | — | ● `type` (drives pre-fill option) | ● available reasons by type | ● submission state |
| 3-tier feedback pipeline | ○ tier (future weighting) | — | ● type (for attribution) | — | ● Layer-3 behaviour window |
| Dashboard metrics | ● tier + archetype distribution | — | ● type distribution | ○ severity | ● appeal rate, outcome split |
| **New · Restriction agreement feedback (task 1.1)** | ● `user_id`, level | — | ● `violation_id`, type | ○ impact (for displayed desc) | — |
| **New · Layer-2 auto-derivation (task 1.2)** | ● `user_id` | — | ● `violation_id` | — | — |
| **New · Evidence submission (task 1.4)** | ● `user_id`, tier | — | ● clip TS, type | — | ● `second_appeal_path_available` |

---

## Section 3 · Phase roadmap · which potential field unlocks which phase

### Phase 2 data unlocks

| Field | Unblocks |
|---|---|
| `content_category` | Archetype refinement beyond the current 5; fine-grained intent taxonomy |
| `multi_modal_signals` | Layer-5 CoV and Layer-7 output classifier training |
| `reviewer_id` / `reviewer_tier` / `reviewer_notes` | Moderator-side AI summarization tool |
| `conversation_continuity_key` (= `(user_id, violation_type)`) | Cross-LIVE AI session aggregation |
| `confidence_score` | "The system was X % confident" transparency |
| `downstream_impacts` (structured) | Precise "What happens now" answers beyond the text label |

### Phase 3 data unlocks

| Field | Unblocks |
|---|---|
| `audience_demographics` | Content-category risk modeling |
| `historical_compliance_score` | Creator risk-scoring (pre-LIVE reminders) |
| `risk_score_pre_live` (derived) | Proactive intervention pipeline |
| Full `multi_modal_signals` | Multimodal LLM direct-to-clip analysis |

---

## Section 4 · Data-quality / governance notes

- **PII desensitisation (§4.2):** any user-typed free text (chat messages, evidence
  submissions) must be PII-scrubbed before entering LLM context. Current demo
  passes everything through; production must add a scrubber.
- **Retention:** PRD-default 90 days. `conversation_id` + all associated
  `messagesByViolation` rows are deleted on account deletion cascade.
- **Cross-border:** follows TikTok's existing data localisation policy; no
  cross-region replication of conversation content.
- **Kids Mode:** all five buckets gate off — feature disabled if
  `user_profile.is_kids_mode == true`.

> **中文治理总结:** 所有创作者自由输入在注入 LLM 前必须脱敏；默认 90 天保留期；账号删除级联；Kids Mode 下整个功能关闭。
