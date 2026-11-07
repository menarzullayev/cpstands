# AI Audit: 08-technical-spec

- Auditor: AI agent (Claude). This is a model judgment, not a human approval.
- Date: 2026-11-08
- Inputs inspected: STAGE contract, OUTPUT.md, quality gate, PRD, domain model, architecture, ADR set, evidence records.
- Result: **WARN**

## Checks
- API, schema, events, authorization, security, performance, integrations, error handling, observability present and traceable to REQ and ADR identifiers: yes.
- Schema constraints implement the domain invariants (unique keys for standings message, reminder offset, event key and delivery): yes.
- Consistency with owner decisions: no external vendor (ADR-009), manual backups (ADR-014), long polling on the home PC (ADR-006): yes.

## Findings
1. WARN: NFR-001, NFR-002, NFR-004 and NFR-005 are targets that need the planned experiment before the freshness promise is public.
2. WARN: Telegram rate figures are second-hand (EVID-009); configuration defaults must be verified.
3. WARN: The Codeforces JSON field names are taken from public documentation and observed responses; contract tests on recorded fixtures are required (NFR-012).
4. WARN: Retention of 30 days is a policy choice with privacy impact and needs explicit owner approval.
5. WARN: Because there is no external heartbeat, alerts depend on the process being alive; the owner accepted this in ADR-009.

## Escalation
HUMAN_APPROVAL_REQUIRED: data, security and privacy-relevant choices (retention, stored fields, authorization model).
