# Global Audit

- Framework version: 1.0.0
- Executed at: 2026-11-07T20:43:07+00:00
- Status: BLOCKED
- Recovery audit: PASS
- Schema audit: PASS
- Integrity audit: BLOCK
- Semantic audit: PASS

## Findings
- BLOCK: 05-domain-model: status is NOT_STARTED, expected PASSED
- BLOCK: 05-domain-model: OUTPUT.md is unchanged from TEMPLATE.md: docs\05-domain-model\OUTPUT.md
- BLOCK: missing handoff: .project-alpha\handoffs\05-domain-model__to__06-architecture.md
- BLOCK: 06-architecture: status is NOT_STARTED, expected PASSED
- BLOCK: 06-architecture: OUTPUT.md is unchanged from TEMPLATE.md: docs\06-architecture\OUTPUT.md
- BLOCK: missing handoff: .project-alpha\handoffs\06-architecture__to__07-adr.md
- BLOCK: 07-adr: status is NOT_STARTED, expected PASSED
- BLOCK: 07-adr: OUTPUT.md is unchanged from TEMPLATE.md: docs\07-adr\OUTPUT.md
- BLOCK: missing handoff: .project-alpha\handoffs\07-adr__to__08-technical-spec.md
- BLOCK: 08-technical-spec: status is NOT_STARTED, expected PASSED
- BLOCK: 08-technical-spec: OUTPUT.md is unchanged from TEMPLATE.md: docs\08-technical-spec\OUTPUT.md
- BLOCK: missing handoff: .project-alpha\handoffs\08-technical-spec__to__09-development-plan.md
- BLOCK: 09-development-plan: status is NOT_STARTED, expected PASSED
- BLOCK: 09-development-plan: OUTPUT.md is unchanged from TEMPLATE.md: docs\09-development-plan\OUTPUT.md
- BLOCK: missing handoff: .project-alpha\handoffs\09-development-plan__to__10-operations.md
- BLOCK: 10-operations: status is NOT_STARTED, expected PASSED
- BLOCK: 10-operations: OUTPUT.md is unchanged from TEMPLATE.md: docs\10-operations\OUTPUT.md
- BLOCK: integrity: decision DEC-001 is approved but has no Approval ID
- BLOCK: integrity: decision DEC-002 is approved but has no Approval ID
- BLOCK: integrity: decision DEC-003 is approved but has no Approval ID
- BLOCK: integrity: decision DEC-004 is approved but has no Approval ID
- BLOCK: integrity: decision DEC-005 is approved but has no Approval ID
- BLOCK: integrity: approval APR-001 missing Decision
- BLOCK: integrity: approval APR-002 missing Decision
- BLOCK: integrity: approval APR-003 missing Decision
- BLOCK: integrity: approval APR-004 missing Decision
- BLOCK: integrity: approval APR-005 missing Decision

## Gate
Resolve all findings and rerun the global audit.
