"""
Compliance report export — generate HTML/JSON compliance reports from the
audit trail.  Zero external dependencies.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def _load_audit_entries(path: Path) -> list[dict]:
    """Load all audit entries from a JSONL file."""
    if not path.exists():
        return []
    entries: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def _compute_stats(entries: list[dict]) -> dict:
    """Compute summary statistics from audit entries."""
    n_total = len(entries)
    n_selected = sum(1 for e in entries if e.get("status") == "selected")
    n_rejected = sum(1 for e in entries if e.get("status") == "rejected")
    n_no_survivors = sum(1 for e in entries if e.get("status") == "no_survivors")
    block_rate = round((n_rejected + n_no_survivors) / max(n_total, 1) * 100, 1)

    # Per-tool breakdown
    tools: dict[str, dict[str, int]] = {}
    for e in entries:
        name = e.get("tool_name") or "unknown"
        if name not in tools:
            tools[name] = {"total": 0, "selected": 0, "rejected": 0}
        tools[name]["total"] += 1
        status = e.get("status", "unknown")
        if status == "selected":
            tools[name]["selected"] += 1
        elif status in ("rejected", "no_survivors"):
            tools[name]["rejected"] += 1

    # Time range
    timestamps = [e.get("timestamp", "") for e in entries if e.get("timestamp")]
    ts_from = min(timestamps) if timestamps else ""
    ts_to = max(timestamps) if timestamps else ""

    return {
        "n_total": n_total,
        "n_selected": n_selected,
        "n_rejected": n_rejected,
        "n_no_survivors": n_no_survivors,
        "block_rate": block_rate,
        "tools": tools,
        "time_from": ts_from,
        "time_to": ts_to,
    }


def _coerce_timestamp(ts: str) -> str:
    """Try to parse an ISO timestamp and return a human-readable form."""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        return ts


# ── public API ────────────────────────────────────────────────────────


def export_json(path: Path, output: Optional[Path] = None) -> dict:
    """Export audit trail as a structured JSON dict.

    Returns the dict (also writes to *output* if provided).
    """
    entries = _load_audit_entries(path)
    stats = _compute_stats(entries)
    report = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "audit_file": str(path),
        "metadata": stats,
        "entries": entries,
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False))
    return report


def export_html(path: Path, output: Optional[Path] = None) -> str:
    """Generate a self-contained HTML compliance report.

    Returns the HTML string (also writes to *output* if provided).
    """
    entries = _load_audit_entries(path)
    stats = _compute_stats(entries)

    bar_chart_css = _bar_chart_css(stats["tools"])

    # Build table rows
    rows_html = ""
    for e in entries[-100:]:  # last 100 entries
        ts = _coerce_timestamp(e.get("timestamp", ""))
        status = e.get("status", "unknown")
        badge = _status_badge(status)
        tool = e.get("tool_name") or "—"
        strategy = e.get("strategy", "—")
        n_cand = e.get("n_candidates", "—")
        n_sel = e.get("n_selected", "—")
        audit_id = e.get("audit_id", "—")
        rows_html += (
            f"<tr><td>{badge}</td><td>{ts}</td><td>{tool}</td>"
            f"<td>{strategy}</td><td>{n_cand}</td><td>{n_sel}</td>"
            f"<td><code>{audit_id}</code></td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>cascade — Compliance Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         max-width: 1000px; margin: 0 auto; padding: 20px; background: #f8f9fa; color: #222; }}
  h1 {{ font-size: 1.6em; margin-bottom: 4px; }}
  .subtitle {{ color: #666; font-size: 0.9em; margin-top: 0; }}
  .summary {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
  .card {{ background: #fff; border-radius: 8px; padding: 16px 20px; flex: 1; min-width: 120px;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .card .num {{ font-size: 2em; font-weight: 700; line-height: 1.2; }}
  .card .label {{ font-size: 0.85em; color: #666; }}
  .card.green .num {{ color: #2e7d32; }}
  .card.red .num {{ color: #c62828; }}
  .card.blue .num {{ color: #1565c0; }}
  h2 {{ font-size: 1.2em; margin: 24px 0 8px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th, td {{ text-align: left; padding: 8px 12px; font-size: 0.9em; }}
  th {{ background: #f0f0f0; font-weight: 600; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600; }}
  .badge.ok {{ background: #e8f5e9; color: #2e7d32; }}
  .badge.fail {{ background: #fbe9e7; color: #c62828; }}
  .badge.warn {{ background: #fff8e1; color: #f57f17; }}
  .bar-chart {{ display: flex; align-items: flex-end; gap: 12px; height: 120px; margin: 12px 0 20px;
               padding: 10px 0; border-bottom: 2px solid #ddd; }}
  .bar {{ flex: 1; min-width: 40px; text-align: center; position: relative; }}
  .bar-inner {{ display: block; width: 100%; border-radius: 4px 4px 0 0; position: relative; }}
  .bar-label {{ font-size: 0.75em; margin-top: 4px; color: #555; white-space: nowrap; overflow: hidden;
                text-overflow: ellipsis; }}
  .bar-count {{ font-size: 0.7em; color: #888; }}
  code {{ background: #f4f4f4; padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }}
  footer {{ margin-top: 24px; font-size: 0.8em; color: #999; text-align: center; }}
</style>
</head>
<body>
<h1>🔍 cascade — Compliance Report</h1>
<p class="subtitle">Audit file: <code>{path}</code> &nbsp;|&nbsp; Exported: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC</p>

<div class="summary">
  <div class="card green"><div class="num">{stats["n_selected"]}</div><div class="label">Selected</div></div>
  <div class="card red"><div class="num">{stats["n_rejected"]}</div><div class="label">Rejected</div></div>
  <div class="card blue"><div class="num">{stats["n_total"]}</div><div class="label">Total Decisions</div></div>
  <div class="card red"><div class="num">{stats["block_rate"]}%</div><div class="label">Block Rate</div></div>
</div>

<h2>Per-Tool Breakdown</h2>
{bar_chart_css}

<h2>Recent Audit Entries (last {min(100, len(entries))})</h2>
<table>
<thead><tr><th>Status</th><th>Timestamp</th><th>Tool</th><th>Strategy</th><th>#Candidates</th><th>#Selected</th><th>Audit ID</th></tr></thead>
<tbody>
{rows_html}
</tbody>
</table>
<footer>cascade v0.6.0 — Generated by cascade audit export</footer>
</body>
</html>"""

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding="utf-8")

    return html


# ── internal helpers ─────────────────────────────────────────────────


def _status_badge(status: str) -> str:
    if status == "selected":
        return '<span class="badge ok">SELECTED</span>'
    elif status in ("rejected", "no_survivors"):
        return '<span class="badge fail">REJECTED</span>'
    return '<span class="badge warn">UNKNOWN</span>'


def _bar_chart_css(tools: dict[str, dict[str, int]]) -> str:
    """Build an inline bar chart using pure CSS (no JS, no images)."""
    if not tools:
        return "<p>No data.</p>"

    max_val = max(t["total"] for t in tools.values()) or 1
    bars_html = ""
    for name, counts in sorted(tools.items()):
        pct = (counts["total"] / max_val) * 100
        selected_pct = (counts["selected"] / max(counts["total"], 1)) * 100
        rejected_pct = (counts["rejected"] / max(counts["total"], 1)) * 100
        bars_html += (
            f'<div class="bar" style="flex-basis:{max(40, min(80, 500 // len(tools)))}px">'
            f'<div class="bar-inner" style="height:{pct}%;'
            f'background:linear-gradient(to top, #c62828 {rejected_pct}%, #2e7d32 {100 - rejected_pct}%);"></div>'
            f'<div class="bar-label">{name}</div>'
            f'<div class="bar-count">{counts["selected"]}/{counts["total"]}</div>'
            f'</div>\n'
        )

    return f'<div class="bar-chart">{bars_html}</div>'
