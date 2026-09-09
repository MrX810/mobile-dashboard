#!/usr/bin/env python3
"""
Dashboard Backend — sammelt Mac, Hermes und OpenRouter Stats
und pusht jede Minute zu Supabase.
"""
import os, sys, json, subprocess, time, datetime, urllib.request, urllib.error
from pathlib import Path

# ===== CONFIG =====
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://YOUR_PROJECT.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "YOUR_SERVICE_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ===== MAC STATS =====
def get_mac_stats():
    """Sammelt CPU, RAM, Disk, Uptime, Battery via macOS Tools."""
    stats = {}

    # CPU
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "hw.ncpu"], text=True
        ).strip()
        stats["cpu_cores"] = int(out)
    except Exception:
        stats["cpu_cores"] = 8

    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "hw.cpufrequency"], text=True
        ).strip()
        stats["cpu_freq"] = f"{int(out) / 1e9:.1f}"
    except Exception:
        stats["cpu_freq"] = "?"

    # CPU Usage (top snapshot)
    try:
        out = subprocess.check_output(
            ["sh", "-c", "top -l 1 -n 0 | grep 'CPU usage'"],
            text=True
        ).strip()
        # "CPU usage: 12.34% user, 5.67% sys, 81.99% idle"
        parts = out.split()
        user_pct = float(parts[2].rstrip("%"))
        sys_pct = float(parts[4].rstrip("%"))
        stats["cpu_percent"] = round(user_pct + sys_pct, 1)
    except Exception:
        stats["cpu_percent"] = 0

    # CPU History (append for sparkline)
    history_file = DATA_DIR / "cpu_history.json"
    try:
        history = json.loads(history_file.read_text()) if history_file.exists() else []
    except Exception:
        history = []
    history.append(stats.get("cpu_percent", 0))
    history = history[-60:]  # keep last 60 readings
    history_file.write_text(json.dumps(history))
    stats["cpu_history"] = history

    # RAM
    try:
        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
        stats["mem_total"] = int(out) // (1024 * 1024)  # MB
    except Exception:
        stats["mem_total"] = 0

    try:
        out = subprocess.check_output(["vm_stat"], text=True)
        page_size = 4096
        import re
        def parse_vm_stat(label):
            match = re.search(rf"{label}\s+(\d+)\.", out)
            return int(match.group(1)) * page_size if match else 0
        free = parse_vm_stat("Pages free:")
        active = parse_vm_stat("Pages active:")
        inactive = parse_vm_stat("Pages inactive:")
        wired = parse_vm_stat("Pages wired down:")
        stats["mem_used"] = (active + wired + inactive) // (1024 * 1024)
    except Exception as e:
        stats["mem_used"] = 0

    # Disk
    try:
        out = subprocess.check_output(["df", "-k", "/"], text=True)
        parts = out.strip().split("\n")[1].split()
        total_kb = int(parts[1])
        used_kb = int(parts[2])
        stats["disk_total"] = total_kb // 1024  # MB
        stats["disk_used"] = used_kb // 1024
    except Exception:
        stats["disk_total"] = 0
        stats["disk_used"] = 0

    # Uptime
    try:
        out = subprocess.check_output(["uptime"], text=True).strip()
        # Parse "up 3 days, 14:22"
        up_idx = out.index("up ") + 3
        up_part = out[up_idx:out.index(",", up_idx) if "," in out[up_idx:] else None]
        stats["uptime"] = up_part.strip()
    except Exception:
        stats["uptime"] = "?"

    # Boot time
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "kern.boottime"], text=True
        ).strip()
        # { sec = 1234567890, usec = 0 } Mon Sep  5 10:30:00 2024
        import re
        match = re.search(r"(\w+ \w+ \d+ \d+:\d+:\d+ \d+)", out)
        if match:
            stats["boot_time"] = match.group(1)
        else:
            stats["boot_time"] = "?"
    except Exception:
        stats["boot_time"] = "?"

    # Battery (stationary Mac — may not have one)
    try:
        out = subprocess.check_output(
            ["pmset", "-g", "batt"], text=True
        )
        if "Battery" in out:
            import re
            pct_match = re.search(r"(\d+)%", out)
            stats["battery_percent"] = int(pct_match.group(1)) if pct_match else None
            stats["battery_charging"] = "charging" in out.lower() or "AC attached" in out
        else:
            stats["battery_percent"] = None
            stats["battery_charging"] = True  # stationary = plugged in
    except Exception:
        stats["battery_percent"] = None
        stats["battery_charging"] = True

    return stats


# ===== HERMES STATUS =====
def get_hermes_stats():
    """Prüft Hermes Gateway Status und aktives Modell."""
    stats = {
        "hermes_online": False,
        "hermes_model": "?"
    }

    # Check gateway process
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "hermes"], text=True
        ).strip()
        stats["hermes_online"] = len(out) > 0
    except Exception:
        stats["hermes_online"] = False

    # Try to read config for model
    try:
        config_path = Path.home() / ".hermes" / "config.yaml"
        if config_path.exists():
            import re
            content = config_path.read_text()
            model_match = re.search(r"model:\s*['\"]?([^'\"#\n]+)", content)
            if model_match:
                stats["hermes_model"] = model_match.group(1).strip()
    except Exception:
        pass

    return stats


# ===== OPENROUTER STATS =====
def get_openrouter_stats():
    """Holt Token-Stats von der OpenRouter API."""
    stats = {
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_requests": 0,
        "cost": 0.0,
        "models": [],
        "heatmap": [],
        "active_day": {},
        "weekly": {},
        "openrouter_online": False
    }

    if not OPENROUTER_KEY:
        return stats

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }

    # Activity / Usage
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/activity",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            stats["openrouter_online"] = True
            # Parse based on OpenRouter response format
            if "data" in data:
                d = data["data"]
                stats["total_tokens"] = d.get("total_tokens", 0)
                stats["input_tokens"] = d.get("input_tokens", 0)
                stats["output_tokens"] = d.get("output_tokens", 0)
                stats["total_requests"] = d.get("total_requests", 0)
                stats["cost"] = d.get("cost", 0.0)
    except Exception as e:
        print(f"OpenRouter activity error: {e}", file=sys.stderr)

    # Models breakdown
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/activity/models",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if "data" in data:
                total = sum(m.get("total_tokens", 0) for m in data["data"])
                stats["models"] = [
                    {
                        "name": m.get("model", "?"),
                        "requests": m.get("requests", 0),
                        "input": m.get("input_tokens", 0),
                        "output": m.get("output_tokens", 0),
                        "cost": m.get("cost", 0.0),
                        "share": round(m.get("total_tokens", 0) / total * 100, 1) if total > 0 else 0
                    }
                    for m in data["data"]
                ]
    except Exception as e:
        print(f"OpenRouter models error: {e}", file=sys.stderr)

    # Heatmap (365 days)
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/activity/heatmap",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if "data" in data:
                stats["heatmap"] = [
                    {"date": d.get("date"), "tokens": d.get("tokens", 0)}
                    for d in data["data"]
                ]
    except Exception as e:
        print(f"OpenRouter heatmap error: {e}", file=sys.stderr)

    # Active day + weekly
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/activity/stats",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if "data" in data:
                d = data["data"]
                ad = d.get("active_day", {})
                stats["active_day"] = {
                    "day": ad.get("day", "?"),
                    "date": ad.get("date", "?"),
                    "tokens": ad.get("tokens", 0)
                }
                stats["weekly"] = d.get("weekly", {})
    except Exception as e:
        print(f"OpenRouter stats error: {e}", file=sys.stderr)

    return stats


# ===== SUPABASE PUSH =====
def push_to_supabase(all_stats):
    """Upsert Stats in Supabase via REST API."""
    payload = json.dumps({
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "mac_online": True,
        **all_stats
    }).encode()

    # Get existing record to upsert
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/dashboard_stats?id=eq.1",
        data=payload,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal,resolution=merge-duplicates"
        },
        method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Pushed to Supabase OK")
            else:
                print(f"Supabase response: {resp.status}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        # If no record exists, insert instead
        if e.code == 404:
            req2 = urllib.request.Request(
                f"{SUPABASE_URL}/rest/v1/dashboard_stats",
                data=json.dumps({"id": 1, **json.loads(payload)}).encode(),
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                },
                method="POST"
            )
            with urllib.request.urlopen(req2, timeout=10):
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Inserted to Supabase OK")
        else:
            raise


# ===== MAIN =====
def main():
    print("Dashboard Backend starting...")

    while True:
        try:
            mac = get_mac_stats()
            hermes = get_hermes_stats()
            or_stats = get_openrouter_stats()

            all_stats = {**mac, **hermes, **or_stats}

            # Also save locally
            (DATA_DIR / "stats.json").write_text(json.dumps(all_stats, indent=2))

            # Push to Supabase
            push_to_supabase(all_stats)

        except Exception as e:
            print(f"Error in cycle: {e}", file=sys.stderr)

        time.sleep(60)


if __name__ == "__main__":
    main()
