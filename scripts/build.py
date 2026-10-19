"""Write every generated part of the repository from evidence/evidence.yml and the ADRs.

  - each ADR's "Evidence" section, from the ids on its "- Evidence:" line
  - the decision table in README.md and decisions/README.md
  - EVIDENCE.md: every figure, its method, and the file it was measured in
  - the cost tables in docs/04-options.md, from results/cost.json

    python scripts/build.py           # write
    python scripts/build.py --check   # fail if anything generated is out of date

It also fails if an ADR cites an unknown evidence id, lacks a section of the template
(decisions/README.md), has an unknown status, or is "Accepted" without evidence.

Every evidence entry also carries a `check`, saying how its value is verified:

  {json: <path>, expr: "<python expression over d>"}   evaluated against the JSON at <path>
                                                        (relative to the repo root); must
                                                        equal the entry's value exactly
  sibling                                               measured and verified in another
                                                        repo's own CI; not re-checked here
  {pending: true, reason: "..."}                        not yet machine-checked, with why
  {job: <name>}                                         verified by the named job in this
                                                        repo's own CI, not by this script

`expr` is evaluated with no builtins except `len`, `sum`, `round`, `str`, `format`, `int`,
`float`, `min` and `max`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITHUB = "https://github.com/technobasant"
SECTIONS = ("## Context", "## Decision drivers", "## Options", "## Decision", "## Consequences",
            "## Revisit when", "## Evidence")  # fmt: skip
STATUSES = ("Accepted", "Proposed", "Superseded")
SAFE_EVAL_NAMES = {"len": len, "sum": sum, "round": round, "str": str, "format": format,
                   "int": int, "float": float, "min": min, "max": max}  # fmt: skip


def check_evidence(evidence: dict) -> list[str]:
    """Verify every evidence entry's `check`. Returns a list of problem strings."""
    problems = []
    for eid, e in evidence.items():
        check = e.get("check")
        if check is None:
            problems.append(f"{eid}: missing 'check'")
        elif check == "sibling":
            pass  # measured and verified in another repo's own CI
        elif isinstance(check, dict) and "pending" in check:
            if not check.get("reason"):
                problems.append(f"{eid}: check: pending needs a reason")
        elif isinstance(check, dict) and "job" in check:
            pass  # verified by a named job in this repo's own CI, not by this script
        elif isinstance(check, dict) and "json" in check and "expr" in check:
            data_path = ROOT / check["json"]
            if not data_path.exists():
                problems.append(f"{eid}: check.json '{check['json']}' does not exist")
                continue
            d = json.loads(data_path.read_text())
            try:
                got = eval(check["expr"], {"__builtins__": SAFE_EVAL_NAMES}, {"d": d})  # noqa: S307
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{eid}: check.expr raised {exc!r}")
                continue
            if str(got) != e["value"]:
                problems.append(f"{eid}: check.expr gives {got!r}, evidence.yml says {e['value']!r}")
        else:
            problems.append(f"{eid}: invalid 'check': {check!r}")
    return problems


def source_url(item: dict) -> str:
    return f"{GITHUB}/{item['repo']}/blob/main/{item['file']}"


def load_evidence() -> dict:
    return yaml.safe_load((ROOT / "evidence" / "evidence.yml").read_text())


def load_adrs() -> list[dict]:
    adrs = []
    for path in sorted((ROOT / "decisions").glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = path.read_text()
        title = re.search(r"^# (\d{4})\. (.+)$", text, re.M)
        status = re.search(r"^- Status: (\w+)", text, re.M)
        cited = re.search(r"^- Evidence:(.*)$", text, re.M)
        if not (title and status and cited):
            raise SystemExit(f"{path.name}: needs a '# NNNN. Title', '- Status:' and '- Evidence:'")
        ids = [i.strip() for i in cited.group(1).split(",") if i.strip()]
        adrs.append({"path": path, "text": text, "number": title.group(1),
                     "title": title.group(2), "status": status.group(1), "evidence": ids})  # fmt: skip
    return adrs


def evidence_block(ids: list[str], evidence: dict) -> str:
    if not ids:
        return "<!-- evidence:start -->\nNot measured yet; see the status above.\n<!-- evidence:end -->"
    lines = ["<!-- evidence:start -->"]
    for i in ids:
        e = evidence[i]
        indirect = f"Indirect: {e['note']}. " if e.get("relation") == "indirect" else ""
        lines.append(f"- {indirect}**{e['value']}** {e['label']}. {e['method'][0].upper()}{e['method'][1:]}. "
                     f"Source: [{e['repo']}/{e['file']}]({source_url(e)})")  # fmt: skip
    lines.append("<!-- evidence:end -->")
    return "\n".join(lines)


def decision_table(adrs: list[dict], evidence: dict, link_prefix: str) -> str:
    rows = ["<!-- decisions:start -->", "| # | Decision | Status | Backed by |", "|---|---|---|---|"]
    for a in adrs:
        backed = "; ".join(f"{evidence[i]['value']} {evidence[i]['label']}" for i in a["evidence"][:2])
        rows.append(f"| {a['number']} | [{a['title']}]({link_prefix}{a['path'].name}) | "
                    f"{a['status']} | {backed or 'modelled, not yet measured'} |")  # fmt: skip
    rows.append("<!-- decisions:end -->")
    return "\n".join(rows)


def checked_text(e: dict) -> str:
    check = e.get("check")
    if check == "sibling":
        return "sibling repo: verified in its own CI"
    if isinstance(check, dict) and "pending" in check:
        return f"pending: {check['reason']}"
    if isinstance(check, dict) and "job" in check:
        return f"verified by the `{check['job']}` CI job, not this script"
    if isinstance(check, dict) and "json" in check:
        return f"machine-checked against `{check['json']}`"
    return "unchecked"


def evidence_page(adrs: list[dict], evidence: dict) -> str:
    cited_by: dict[str, list[str]] = {}
    for a in adrs:
        for i in a["evidence"]:
            cited_by.setdefault(i, []).append(f"[{a['number']}](decisions/{a['path'].name})")
    out = [
        "# Evidence",
        "",
        "Every figure the decisions cite, with how it was measured, the file it came from, and "
        "how `scripts/build.py --check` verifies it today. Generated by `scripts/build.py` from "
        "[`evidence/evidence.yml`](evidence/evidence.yml); do not edit by hand.",
        "",
        "| Figure | What it is | How it was measured | Source | Cited by | Checked |",
        "|---|---|---|---|---|---|",
    ]
    for i, e in evidence.items():
        source = f"[{e['repo']}/{e['file']}]({source_url(e)})"
        citing = ", ".join(cited_by.get(i, [])) or "—"
        label = f"Indirect: {e['note']}. {e['label']}" if e.get("relation") == "indirect" else e["label"]
        out.append(f"| **{e['value']}** | {label} | {e['method']} | {source} | {citing} | "
                   f"{checked_text(e)} |")  # fmt: skip
    return "\n".join(out) + "\n"


def cost_tables() -> str:
    r = json.loads((ROOT / "results" / "cost.json").read_text())
    tiers = list(r["tiers"].values())
    out = [
        "<!-- cost:start -->",
        f"List prices retrieved {r['prices_retrieved']} ([`cost/prices.yml`](../cost/prices.yml)).",
        "",
        "**Break-even.** One hour of a medium-sized engine costs the same as scanning this much on a "
        "per-scan engine. Below it, per-scan is cheaper; above it, paying for the hour is.",
        "",
        "| Engine paid by the hour | USD per hour | BigQuery on-demand | Athena |",
        "|---|---:|---:|---:|",
    ]
    for engine, b in r["break_even"].items():
        t = b["tb_per_hour"]
        out.append(
            f"| {engine} | ${b['usd_per_hour']:.2f} | {t['BigQuery on-demand']} TB | {t['Athena']} TB |"
        )
    out += [
        "",
        "**The client's scale**, today and in its growth plan, under the assumptions in "
        "[`cost/workloads.yml`](../cost/workloads.yml). The vendor bill for the analytical layer, "
        "per month:",
        "",
        "| Option | Today | In 12 months | In 36 months |",
        "|---|---:|---:|---:|",
    ]
    for o in tiers[0]["monthly_usd"]:
        out.append(f"| {o} | " + " | ".join(f"${t['monthly_usd'][o]['total']:,}" for t in tiers) + " |")
    ratio = " | ".join(str(t["assumed_tb_scanned_per_engine_hour"]) for t in tiers)
    out.append(f"| *assumed TB scanned per engine-hour* | {ratio} |")
    out.append("| *stored TB* | " + " | ".join(str(t["storage_tb"]) for t in tiers) + " |")
    out += [
        "",
        "**With the people to run it**: the bill plus the share of an engineer each option is "
        "assumed to take, per month:",
        "",
        "| Option | Today | In 12 months | In 36 months |",
        "|---|---:|---:|---:|",
    ]
    for o in tiers[0]["monthly_usd"]:
        out.append(
            f"| {o} | "
            + " | ".join(f"${t['monthly_usd'][o]['total_with_operations']:,}" for t in tiers)
            + " |"
        )
    out.append("<!-- cost:end -->")
    return "\n".join(out)


def replace_block(text: str, name: str, block: str) -> str:
    pattern = re.compile(rf"<!-- {name}:start -->.*?<!-- {name}:end -->", re.S)
    if not pattern.search(text):
        raise SystemExit(f"missing <!-- {name}:start --> … <!-- {name}:end --> block")
    return pattern.sub(lambda _: block, text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    evidence, adrs = load_evidence(), load_adrs()

    problems = check_evidence(evidence)
    for a in adrs:
        for section in SECTIONS:
            if section not in a["text"]:
                problems.append(f"{a['path'].name}: missing '{section}'")
        for i in a["evidence"]:
            if i not in evidence:
                problems.append(f"{a['path'].name}: unknown evidence id '{i}'")
        if a["status"] not in STATUSES:
            problems.append(f"{a['path'].name}: status must be one of {', '.join(STATUSES)}")
        if a["status"] == "Accepted" and not a["evidence"]:
            problems.append(f"{a['path'].name}: an Accepted decision must cite evidence")
    if problems:
        sys.exit("\n".join(problems))

    outputs: dict[Path, str] = {}
    for a in adrs:
        outputs[a["path"]] = replace_block(a["text"], "evidence", evidence_block(a["evidence"], evidence))
    for path, prefix in ((ROOT / "README.md", "decisions/"), (ROOT / "decisions" / "README.md", "")):
        outputs[path] = replace_block(path.read_text(), "decisions", decision_table(adrs, evidence, prefix))
    outputs[ROOT / "EVIDENCE.md"] = evidence_page(adrs, evidence)
    guide = ROOT / "docs" / "04-options.md"
    outputs[guide] = replace_block(guide.read_text(), "cost", cost_tables())

    stale = [p for p, text in outputs.items() if not p.exists() or p.read_text() != text]
    if args.check:
        if stale:
            sys.exit(
                "out of date, run scripts/build.py: " + ", ".join(str(p.relative_to(ROOT)) for p in stale)
            )
        print(f"up to date: {len(adrs)} decisions, {len(evidence)} figures")
        return
    for p in stale:
        p.write_text(outputs[p])
    print(f"wrote {len(stale)} file(s)")


if __name__ == "__main__":
    main()
