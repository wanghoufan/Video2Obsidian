#!/usr/bin/env python3
"""S0-T01 environment collection. Prints JSON to stdout. Exit 0 always (records gaps as null)."""
import json, platform, subprocess, sys, os

def sh(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return (out.stdout + out.stderr).strip()
    except Exception as e:
        return f"ERROR: {e}"

def pip_show(pkg):
    out = sh([sys.executable, "-m", "pip", "show", pkg])
    ver = None
    for line in out.splitlines():
        if line.startswith("Version:"):
            ver = line.split(":", 1)[1].strip()
    return ver

env = {
    "os_product": sh(["sw_vers", "-productName"]).splitlines(),
    "os_version": sh(["sw_vers", "-productVersion"]),
    "os_build": sh(["sw_vers", "-buildVersion"]),
    "chip": sh(["uname", "-m"]),
    "model": [l.strip() for l in sh(["system_profiler", "SPHardwareDataType"]).splitlines()
              if "Model Name" in l or "Chip" in l or "Memory" in l],
    "python": platform.python_version(),
    "python_exe": sys.executable,
    "ffmpeg": sh(["ffmpeg", "-version"]).splitlines()[0] if sh(["which", "ffmpeg"]) else None,
    "pip_freeze_file": None,
}
pkgs = {}
for p in ["mlx", "mlx-whisper", "watchdog", "onnxruntime", "silero-vad", "numpy", "torch", "huggingface_hub"]:
    pkgs[p] = pip_show(p)
env["packages"] = pkgs

# mlx-whisper source commit: best effort via pip direct_url + package metadata
env["mlx_whisper_direct_url"] = sh(
    [sys.executable, "-c",
     "from importlib.metadata import distribution; d=distribution('mlx-whisper'); "
     "print([f for f in (d.read_text('direct_url.json') or '').splitlines()])"])

print(json.dumps(env, indent=2, ensure_ascii=False))
