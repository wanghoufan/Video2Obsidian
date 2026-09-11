#!/usr/bin/env python3
"""S0-T07 Silero VAD candidate comparison on a 16k mono wav.
Usage: s0_vad.py <run_id> <wav16k> <outdir> -> prints JSON. Exit 0.
Compares speech ratio at thresholds 0.3/0.5/0.7 + runtime. No audio filtering.
"""
import json, os, sys, time
import numpy as np

def main():
    run_id, wav, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    import subprocess
    # ensure 16k mono float32
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", wav,
                          "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                          "-f", "s16le", "pipe:1"],
                         capture_output=True, timeout=3600)
    if raw.returncode != 0:
        print(json.dumps({"run_id": run_id, "status": "FAIL", "error": raw.stderr.decode()[-500:]}))
        return 2
    audio = np.frombuffer(raw.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    dur = len(audio) / 16000.0

    from silero_vad import load_silero_vad, get_speech_timestamps
    t0 = time.time()
    model = load_silero_vad()
    t1 = time.time()
    cands = {}
    for thr in (0.3, 0.5, 0.7):
        ta = time.time()
        ts = get_speech_timestamps(audio, model, threshold=thr, return_seconds=True)
        tb = time.time()
        speech = sum(s["end"] - s["start"] for s in ts)
        cands[str(thr)] = {"n_segments": len(ts), "speech_s": round(speech, 1),
                           "speech_ratio": round(speech / dur, 4),
                           "infer_s": round(tb - ta, 1)}
    rec = {"run_id": run_id, "status": "OK", "audio_s": round(dur, 1),
           "vad_model": "silero-vad package inclusions (onnx)",
           "model_load_s": round(t1 - t0, 1), "candidates": cands}
    with open(os.path.join(outdir, f"{run_id}.json"), "w") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(json.dumps(rec, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
