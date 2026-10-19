# Principles

Rules that hold across the decisions, rather than being one of them. Each comes from a
result that went wrong in a lab first.

- **The product comes first.** Nothing analytical may slow, lock or fill the product's
  database. When the two conflict, the analytical side gives way: a cancelled report, a
  dropped slot, a stale dashboard.
- **Keep history where it is cheapest to get.** Read changes from the database's log, and
  model every attribute a fact is reported by as Type 2. A periodic copy never sees a
  change undone between two copies.
- **Files are immutable; loads write by key.** Duplicates and corrections resolve in a
  `MERGE`, never by trusting a loader to read a file twice or once.
- **Load by window, replace by window.** Every run knows exactly which period it writes, and
  replaces only that, so re-runs and backfills are ordinary.
- **Wrong data and missing data need different checks.** Rows are tested for values; days
  are checked against what the producer said it sent.
- **Tests must be seen to fail.** A test nobody has seen fail is not known to work; CI breaks
  the models on purpose.
- **Governance is a property of the data, not of the query.** Classification travels with
  the column, from contract to catalog tag to masking policy.
- **One copy, open format, the client's account.** Engines can change; the history should
  not have to move.
- **Measure before deciding, and fix the criteria first.** A choice between platforms is a
  measurement with weights written down before the run.
- **Managed before self-run, until the team is large enough to own it.** The cheapest bill
  is not the cheapest platform.
