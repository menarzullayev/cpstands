# AI Audit: 06-architecture

- Auditor: AI agent (Claude). This is a model judgment, not a human approval.
- Date: 2026-11-08
- Inputs inspected: STAGE contract, OUTPUT.md, quality gate, PRD, domain model, evidence EVID-001 to EVID-015.
- Result: **WARN**

## Checks
- Context, containers, components, deployment, data flow, integrations, security boundaries, reliability, trade-offs, traceability: present.
- Constraints respected: no API-key collection, no server-side standings filtering, rate budgets, public-handle data only.
- Contradictions with PRD, domain model or owner decisions: none. Home-PC hosting is stated as an interim beta with an explicit limit.

## Findings
1. WARN: REQ-N04 (99.9 percent) cannot be met on a home PC; the document restricts that host to a closed beta and requires a proper host before public launch.
2. WARN: the 60 s freshness target (REQ-N01) depends on fetching 0.5 to 7 MB responses at a safe cadence; a load and cadence experiment is required in stage 08 or 09 before the target is promised.
3. WARN: Telegram rate-limit figures (EVID-009) are second-hand; verify before fixing notifier budgets.
4. WARN: no second alert channel exists if the bot is down; an external heartbeat is planned but unspecified.
5. WARN: the 12 numbered decisions (AD-1 to AD-10) become formal records in stage 07; Serverless is rejected on documented facts that may change.

## Escalation
HUMAN_APPROVAL_REQUIRED: major architecture, hosting and vendor choices.

## Addendum after the owner's answers (2026-11-08)
- The owner kept the home PC for the first public release and chose no formal availability target. Finding 1 is therefore resolved by amending
  METRIC-004 (stage 01) and REQ-N04 (stage 04) with explicit notes, not by changing the host. Residual risk: users may expect reliability; mitigations are
  public best-effort wording, published availability, host hardening, an external heartbeat and an owner alert.
- Downstream stages 07 to 10 must reflect the amended availability wording.
