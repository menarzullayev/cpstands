# Record link correction

- Date: 2026-11-08
- Cause: decision records were created without `--approval-id` and approval records without the decision text, so the integrity audit blocked the global audit.
- Fix: the missing fields (`Approval ID` in DEC-001 to DEC-010, `Decision` in APR-001 to APR-010) were appended to the canonical Markdown records. DEC-n is linked to APR-n.
- Not changed: event history, approval timestamps, approvers, stage states. No approval was added or altered.
