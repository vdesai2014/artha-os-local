"""artha status — aggregated liveness probe across nats/local_tool/supervisor/services.

Ground-truth sources:
  nats          → TCP connect to localhost:<port>
  local_tool    → state file + GET /api/health
  supervisor    → .artha/run/supervisor.json + probe_supervisor()
  services      → services.yaml enumeration ∪ .artha/run/services/*.json + probe_service()
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

from cli.common import (
    DEFAULT_LOCAL_TOOL_URL,
    bold,
    dim,
    find_repo_root,
    green,
    load_services_yaml,
    local_tool_url,
    nats_url,
    read_local_tool_state,
    red,
    runtime_dir,
    yellow,
)
from core.supervision import load_supervisor_state, probe_service, probe_supervisor
from supervisor.platform import get_platform_adapter


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

def _probe_tcp(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _probe_nats(url: str) -> dict:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 4222
    alive = _probe_tcp(host, port)
    return {"alive": alive, "url": f"{host}:{port}"}


def _probe_local_tool(root: Path, url: str) -> dict:
    state = read_local_tool_state(root)
    try:
        resp = httpx.get(f"{url}/api/health", timeout=0.5)
        health_ok = resp.status_code == 200
    except httpx.RequestError:
        health_ok = False
    return {"alive": health_ok, "url": url, "state": state}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _tag(alive: bool, label_alive: str = "running", label_dead: str = "down") -> str:
    return green(label_alive) if alive else red(label_dead)


def _fmt_hb_age(hb_age_s: float | None) -> str:
    if hb_age_s is None:
        return dim("—")
    if hb_age_s < 10:
        return f"hb {hb_age_s:.1f}s"
    return yellow(f"hb {hb_age_s:.1f}s")


def _render_human(report: dict) -> None:
    n = report["nats"]
    print(f"nats          {_tag(n['alive'])}   {n['url']}")

    lt = report["local_tool"]
    extra = []
    if lt.get("state"):
        extra.append(f"pid {lt['state'].get('pid')}")
    print(f"local_tool    {_tag(lt['alive'])}   {lt['url']}   " + " ".join(extra))

    sv = report["supervisor"]
    if sv["alive"]:
        p = sv["payload"] or {}
        bits = [f"pid {p.get('pid')}", _fmt_hb_age(sv["hb_age_s"])]
        sid = p.get("session_id")
        if sid:
            bits.append(dim(f"session {sid[:8]}..."))
        print(f"supervisor    {_tag(True)}   {'   '.join(bits)}")
    else:
        print(f"supervisor    {_tag(False)}   {dim(sv.get('reason') or 'unknown')}")

    services = report["services"]
    print()
    print(bold(f"services ({len(services)}):"))
    if not services:
        print(dim("  (none defined in services.yaml)"))
        return
    name_width = max(len(s["name"]) for s in services)
    for svc in services:
        name = svc["name"].ljust(name_width)
        if svc["state_source"] == "orphan":
            print(f"  {name}  {yellow('orphan')}   {dim('state file present but not in services.yaml')}")
            continue
        if not svc["alive"]:
            reason = svc.get("reason") or "never started"
            print(f"  {name}  {red('down')}      {dim(reason)}")
            continue
        p = svc["payload"] or {}
        bits = [f"pid {p.get('child_pid')}", _fmt_hb_age(svc["hb_age_s"])]
        status = p.get("status")
        if status and status != "running":
            bits.append(yellow(status))
        print(f"  {name}  {green('running')}   {'   '.join(bits)}")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(args) -> int:
    root = find_repo_root()
    services_cfg = load_services_yaml(root)
    platform = get_platform_adapter()
    rt_dir = runtime_dir(root)

    # NATS
    nats_info = _probe_nats(nats_url(root))

    # local_tool
    lt_info = _probe_local_tool(root, local_tool_url(root))

    # supervisor
    sup_info = probe_supervisor(rt_dir, platform)

    # services — union of declared and state-file-present
    declared = list(services_cfg.keys())
    state_names: list[str] = []
    services_dir = rt_dir / "services"
    if services_dir.is_dir():
        state_names = sorted(p.stem for p in services_dir.glob("*.json"))
    all_names = list(dict.fromkeys([*declared, *state_names]))

    services_report: list[dict] = []
    for name in all_names:
        if name not in services_cfg and name in state_names:
            services_report.append({"name": name, "state_source": "orphan"})
            continue
        probe = probe_service(rt_dir, name, platform)
        services_report.append({
            "name": name,
            "state_source": "declared",
            **probe,
        })

    report = {
        "nats": nats_info,
        "local_tool": lt_info,
        "supervisor": sup_info,
        "services": services_report,
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _render_human(report)

    # Exit code: non-zero if anything critical is down.
    critical_down = (
        not nats_info["alive"]
        or not lt_info["alive"]
        or not sup_info["alive"]
        or any(s["state_source"] == "declared" and not s.get("alive") for s in services_report)
    )
    return 1 if critical_down else 0
