# AI Audit: idea-selection

- Auditor: AI agent (Claude). This is a model judgment, not a human approval.
- Date: 2026-11-08
- Inputs inspected: STAGE contract, OUTPUT.md, quality gate, evidence EVID-001 to EVID-013, project config.
- Result: **WARN**

## Checks
- Explicit criteria and a comparison of five candidates: present.
- Material claims backed by risk-based evidence: present (13 records, sources and dates).
- Assumptions and uncertainty visible: present.
- Alternatives recorded with reasons: present.
- Contradictions with other documents: none found (no upstream documents exist yet).

## Findings
1. WARN: demand outside Uzbekistan is an assumption, not a measurement. It must be tested in stage 02 and 03.
2. WARN: written terms for kep.uz are missing (EVID-011 is an ASSUMPTION). The dependency is acceptable for planning,
   but production use of that source needs written confirmation.
3. WARN: the weighted scores are the agent's judgment; the human approver should challenge them.

## Escalation
HUMAN_APPROVAL_REQUIRED: idea selection is a high-impact decision and needs an explicit human approval record.
