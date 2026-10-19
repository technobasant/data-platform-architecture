# Risks

Owned, rated and watched. Likelihood and impact are high, medium or low; a risk is closed
when its trigger can no longer happen, not when it has not happened yet.

| # | Risk | Likelihood | Impact | Owner | Mitigation | Trigger to act |
|---|---|---|---|---|---|---|
| R1 | A stalled CDC slot retains WAL until the product's database runs out of disk | low | high | data lead | WAL alarm to the product's on-call; drop the slot rather than risk the product ([9. Operations](09-operations.md)) | retained WAL above 20% of free storage |
| R2 | An RDS failover or major upgrade loses the CDC slot, leaving a gap in history | medium | medium | data lead | re-snapshot runbook; gaps recorded; upgrades planned with product | connector error after a failover |
| R3 | Finance does not trust revenue by plan because it changed | high | high | CFO | the reconciliation shows every moved invoice and why ([8. Migration](08-migration.md)) | sign-off withheld at the first month-end |
| R4 | A corrected file is re-sent under the same name and never loaded | medium | medium | finance systems | contract: immutable files; manifest check holds truncated days ([0003](../decisions/0003-files-immutable-loads-by-key.md)) | a manifest mismatch |
| R5 | The platform bill grows faster than usage | medium | medium | data lead | budgets and alerts; per-job attribution; monthly re-projection | spend above 80% of pro-rata |
| R6 | A missing tag or row filter exposes one customer's data to another | low | high | security lead | tag coverage and isolation tests block deploys ([0011](../decisions/0011-tags-drive-masking-and-row-filters.md)) | any isolation test failure |
| R7 | An erasure misses a copy (time travel, fail-safe, an export, an old dump) | medium | high | security lead | retention set for day 30; proof query; old dumps deleted ([0012](../decisions/0012-erasure.md)) | a proof query that finds anything |
| R8 | The Databricks PostgreSQL connector stays in preview | medium | low | data lead | AWS DMS as the default on Databricks until it is generally available ([0002](../decisions/0002-cdc-from-the-product-database.md)) | the platform choice is Databricks |
| R9 | The two data engineers are hired late | medium | medium | CTO | waves 2–4 stretch; stage 2 moves; managed services keep the load low | not hired by month 4 |
| R10 | The product team cannot take on the event stream for stage 2 | medium | medium | VP Product | usage page stays on the primary; stage 2 slips | not scheduled by month 5 |
| R11 | Vendor lock-in raises the cost of leaving | low | medium | CTO | open table format in the client's bucket ([0006](../decisions/0006-open-format-in-the-clients-account.md)) | a renewal quote above budget |
| R12 | A bucket, key or Terraform mistake destroys the platform's only copy of history older than 90 days | low | high | data lead | AWS Backup into a vault in a separate AWS account, 14 days' retention; a KMS key policy that denies `ScheduleKeyDeletion` except to a break-glass role ([0015](../decisions/0015-restore-points.md)) | a restore drill that cannot recover a dropped table or bucket |
