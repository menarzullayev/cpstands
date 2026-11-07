# Global Audit

- Framework version: 1.0.0
- Executed at: 2026-11-07T20:35:45+00:00
- Status: BLOCKED
- Recovery audit: PASS
- Schema audit: PASS
- Integrity audit: BLOCK
- Semantic audit: BLOCKED

## Findings
- BLOCK: 01-vision: status is REVIEW, expected PASSED
- BLOCK: missing handoff: .project-alpha\handoffs\01-vision__to__02-problem-discovery.md
- BLOCK: 02-problem-discovery: status is NOT_STARTED, expected PASSED
- BLOCK: 02-problem-discovery: OUTPUT.md is unchanged from TEMPLATE.md: docs\02-problem-discovery\OUTPUT.md
- BLOCK: missing handoff: .project-alpha\handoffs\02-problem-discovery__to__03-market-research.md
- BLOCK: 03-market-research: status is NOT_STARTED, expected PASSED
- BLOCK: 03-market-research: OUTPUT.md is unchanged from TEMPLATE.md: docs\03-market-research\OUTPUT.md
- BLOCK: missing handoff: .project-alpha\handoffs\03-market-research__to__04-prd.md
- BLOCK: 04-prd: status is NOT_STARTED, expected PASSED
- BLOCK: 04-prd: OUTPUT.md is unchanged from TEMPLATE.md: docs\04-prd\OUTPUT.md
- BLOCK: missing handoff: .project-alpha\handoffs\04-prd__to__05-domain-model.md
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
- BLOCK: integrity: approval APR-001 missing Decision
- BLOCK: semantic: forward reference DEC-001.md: docs\idea-selection\OUTPUT.md references DEC owned by later stage 07-adr
- BLOCK: semantic: traceability warning 02-problem-discovery: no PROB-* semantic IDs found for required link to 01-vision
- BLOCK: semantic: traceability warning 02-problem-discovery: no METRIC-* semantic IDs found for required link to 01-vision
- BLOCK: semantic: traceability warning 03-market-research: no PROB-* semantic IDs found for required link to 02-problem-discovery
- BLOCK: semantic: traceability warning 04-prd: no PROB-* semantic IDs found for required link to 02-problem-discovery
- BLOCK: semantic: traceability warning 05-domain-model: no REQ-* semantic IDs found for required link to 04-prd
- BLOCK: semantic: traceability warning 06-architecture: no REQ-* semantic IDs found for required link to 04-prd
- BLOCK: semantic: traceability warning 07-adr: no REQ-* semantic IDs found for required link to 04-prd
- BLOCK: semantic: traceability warning 08-technical-spec: no REQ-* semantic IDs found for required link to 04-prd
- BLOCK: semantic: traceability warning 08-technical-spec: no ADR-* semantic IDs found for required link to 07-adr
- BLOCK: semantic: traceability warning 09-development-plan: no REQ-* semantic IDs found for required link to 04-prd
- BLOCK: semantic: traceability warning 09-development-plan: no ADR-* semantic IDs found for required link to 07-adr
- BLOCK: semantic: traceability warning 10-operations: no REQ-* semantic IDs found for required link to 04-prd

## Gate
Resolve all findings and rerun the global audit.
