"""Plain-text output for runs. Every number and ID printed comes from the stored Result."""

from typing import List

from contracts import Verdict

from .client import Run

EXIT_CODE = {Verdict.PASS: 0, Verdict.FAIL: 1, Verdict.ERROR: 2}


def short_id(run_id: str) -> str:
    return run_id[4:] if run_id.startswith("run_") else run_id


def fault_label(fault: str) -> str:
    code, _, rest = fault.partition("_")
    words = rest.replace("_", " ").lower()
    return f"{code} {words[:1].upper()}{words[1:]}"


def describe_error(rule: str, message: str) -> str:
    if rule == "target_reachable":
        return "The demo shop didn't answer, so the test could not run. Start the shop (`make demo`) and run it again."
    return "The engine could not finish this run." + (f" ({message})" if message else "")


def exit_code(run: Run) -> int:
    """0 = PASS, 1 = FAIL (a real problem found), 2 = no verdict (error, still running)."""
    return EXIT_CODE[run.result.verdict] if run.result else 2


def _table(rows: List[List[str]]) -> List[str]:
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip() for r in rows]


def render_report(run: Run) -> str:
    sc, res = run.scenario, run.result
    lines = [
        f"Run {short_id(run.run_id)}   {fault_label(sc.fault.value)}",
        f"Where:     {sc.target_call.file}:{sc.target_call.line}" + (f" ({sc.target_call.method})" if sc.target_call.method else ""),
        f"Injected:  {sc.inject.action} on {sc.inject.on}",
    ]
    if run.rerun_of:
        lines.append(f"Re-run of: {short_id(run.rerun_of)}")
    if run.fix and run.fix.get("patch_sha256"):
        proposal = run.fix.get("proposal") or {}
        lines.append(f"Patch:     {proposal.get('bug_id', 'unknown')} ({proposal.get('source', 'unknown')})")
        lines.append(f"SHA-256:   {run.fix['patch_sha256']}")
    if res is None:
        return "\n".join(lines + ["", f"Status:    {run.status.upper()}. No verdict yet."])

    lines += ["", f"Verdict:   {res.verdict.value}"]
    if res.verdict == Verdict.ERROR:
        lines.append(describe_error(res.rule, res.error_message or ""))
        lines.append("No verdict was reached, so nothing is proven either way.")
        return "\n".join(lines)

    lines.append(f"Result:    {res.money_impact}")
    obs, exp = res.observed, sc.expect
    rows = [["", "Expected", "Observed"], ["PayPal captures", str(exp.captures_per_purchase), str(obs.captures)]]
    if obs.app_recorded_captures is not None:
        rows.append(["App captures", str(obs.captures), str(obs.app_recorded_captures)])
    rows.append([f"Amount ({exp.currency})", exp.amount or "-", obs.amount_captured])
    lines += [""] + _table(rows) + ["", f"Rule:      {res.rule}"]
    ev = res.evidence
    for title, ids in (("PayPal orders", ev.paypal_order_ids), ("PayPal captures", ev.paypal_capture_ids),
                       ("PayPal refunds", ev.paypal_refund_ids), ("Webhook events", ev.webhook_event_ids)):
        if ids:
            lines.append(f"{title}:".ljust(18) + ", ".join(ids))
    return "\n".join(lines)


def render_list(runs: List[Run]) -> str:
    if not runs:
        return "No runs yet. Start one with: python -m cli run"
    rows = [["RUN", "FAULT", "VERDICT", "PAYPAL/APP", "RESULT"]]
    for r in runs:
        res = r.result
        obs = res.observed if res else None
        counts = "-" if not obs or res.verdict == Verdict.ERROR else (
            f"{obs.captures}/{obs.app_recorded_captures if obs.app_recorded_captures is not None else '?'}")
        rows.append([short_id(r.run_id), fault_label(r.scenario.fault.value), res.verdict.value if res else "RUNNING", counts,
                     (res.money_impact if res and res.verdict != Verdict.ERROR else "") if res else ""])
    return "\n".join(_table(rows))
