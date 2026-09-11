#!/usr/bin/env python3
"""S0-T02 dataset probe. Usage: s0_dataset.py <file...> -> JSON lines to stdout."""
import json, subprocess, sys, os

def probe(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size:stream=codec_name,width,height,sample_rate,channels,codec_type",
             "-of", "json", path],
            capture_output=True, text=True, timeout=120)
        return json.loads(out.stdout)
    except Exception as e:
        return {"error": str(e)}

for path in sys.argv[1:]:
    info = probe(path)
    try:
        size = os.path.getsize(path)
    except OSError:
        size = None
    print(json.dumps({"file": path, "bytes": size, "probe": info}, ensure_ascii=False))
