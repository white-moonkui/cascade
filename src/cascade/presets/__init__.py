"""
Rule presets — ready-to-use rule collections for common governance scenarios.

Usage::

    from cascade.presets import DANGEROUS_TOOLS, CODE_EXECUTION
    from cascade import DecisionPipeline

    pipe = DecisionPipeline()
    pipe.set_gate_rules(DANGEROUS_TOOLS + CODE_EXECUTION)
"""

from __future__ import annotations

from typing import Any


def _r(field: str, op: str, value: Any) -> dict:
    return {"field": field, "op": op, "value": value}


# ── presets ───────────────────────────────────────────────────────────

DANGEROUS_TOOLS: list[dict] = [
    _r("name", "nin", [
        "delete_file", "rm", "shred", "format_disk", "dd",
        "exec_command", "shell_exec", "os_system", "subprocess",
        "eval", "exec", "compile",
        "shutdown", "reboot", "poweroff",
        "chmod", "chown", "su", "sudo",
        "iptables", "ufw", "firewall_cmd",
    ]),
]
"""Blocklist of tools that can destroy system integrity."""

CODE_EXECUTION: list[dict] = [
    _r("name", "nin", [
        "exec_command", "shell_exec", "os_system", "subprocess",
        "eval", "exec", "compile", "exec_python", "exec_bash",
        "popen", "run_shell", "run_command",
    ]),
]
"""Blocklist of tools that execute arbitrary code."""

FILE_OPS: list[dict] = [
    _r("name", "nin", [
        "delete_file", "rm", "shred", "truncate",
        "write_file", "overwrite_file",
        "chmod", "chown",
    ]),
]
"""Blocklist of dangerous file operations."""

NETWORK_ACCESS: list[dict] = [
    _r("name", "nin", [
        "http_request", "curl", "wget", "fetch_url",
        "post_data", "api_call", "webhook",
        "ssh_connect", "scp", "rsync",
        "dns_query", "nslookup", "dig",
        "s3_upload", "s3_download",
    ]),
]
"""Blocklist of network-access tools (data exfiltration vector)."""

DATA_EXFILTRATION: list[dict] = [
    _r("name", "nin", [
        "email_send", "send_email",
        "http_post", "post_data",
        "s3_upload", "gcs_upload",
        "ftp_upload", "scp", "rsync",
        "webhook_send", "slack_post",
        "dns_tunnel",
    ]),
]
"""Blocklist of tools commonly used for data exfiltration."""

PRIVILEGED_ACTIONS: list[dict] = [
    _r("name", "nin", [
        "su", "sudo", "runas",
        "chmod", "chown", "usermod",
        "groupadd", "useradd", "passwd",
    ]),
]
"""Blocklist of privilege-escalation / account-management tools."""

ALL_PRESETS: dict[str, list[dict]] = {
    "dangerous_tools": DANGEROUS_TOOLS,
    "code_execution": CODE_EXECUTION,
    "file_ops": FILE_OPS,
    "network_access": NETWORK_ACCESS,
    "data_exfiltration": DATA_EXFILTRATION,
    "privileged_actions": PRIVILEGED_ACTIONS,
}
"""Dict mapping preset names to their rule lists."""


def load_presets(*names: str) -> list[dict]:
    """Load one or more presets by name.

    >>> rules = load_presets("dangerous_tools", "code_execution")
    """
    rules: list[dict] = []
    for name in names:
        if name not in ALL_PRESETS:
            raise KeyError(
                f"Unknown preset: {name!r} "
                f"(available: {list(ALL_PRESETS)})"
            )
        rules.extend(ALL_PRESETS[name])
    return rules
