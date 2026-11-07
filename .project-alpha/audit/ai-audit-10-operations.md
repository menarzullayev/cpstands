# AI Audit: 10-operations

- Auditor: AI agent (Claude). This is a model judgment, not a human approval.
- Date: 2026-11-08
- Inputs inspected: STAGE contract, OUTPUT.md, quality gate, all upstream outputs, ADR set, specification, development plan, owner decisions.
- Result: **WARN**

## Checks
- Test strategy, CI/CD, monitoring, logging, alerting, backup, DR, runbooks, incident readiness, security/compliance, release/rollback, launch criteria present: yes.
- Consistent with owner decisions (home PC, no external heartbeat, manual backups, best-effort availability): yes.
- Every R1 requirement is tested at some level: yes (test strategy table).

## Findings
1. WARN: detection of full-host outages depends entirely on the owner's attention (ADR-009); stated openly in monitoring and incident sections.
2. WARN: Codeforces terms of use are unreviewed; this is launch criterion 9 and must not be skipped.
3. WARN: launch criteria are checkable only after implementation; this stage approves the documentation and the criteria, not the launch.
4. WARN: manual dumps are personal data; the 30-day rule is an operational obligation that no automation enforces.
5. WARN: runbooks do not exist yet; they are scheduled in milestone M7.

## Escalation
HUMAN_APPROVAL_REQUIRED: operational commitments (best effort, manual deploy, no external alerting, no automated backups) and the production launch criteria.

## Addendum after the owner's answers (2026-11-08)
- The owner chose deployment through a self-hosted GitHub runner after the risk was explained. GitHub documents that such runners should almost never serve public
  repositories (EVID-018). The plan now confines the runner (build elsewhere, tag-only deploy workflow, protected environment, fork-workflow approval, unprivileged account,
  pinned actions) and adds launch criterion 13 with a negative test. ADR-015 records the decision.
- Residual risk: HIGH if any confinement measure is misconfigured; the manual script remains as a fallback. Result stays WARN.
