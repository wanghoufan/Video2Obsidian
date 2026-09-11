#!/usr/bin/env python3
"""S0 generic benchmark run harness.
Extracts audio (temp wav or pipe->numpy), runs mlx_whisper.transcribe, records metrics JSON.
Usage: s0_run.py <run_id> <media> [--model REPO] [--word-ts] [--prompt FILE] [--clip START,END,...]
       [--no-speech-thr F] [--audio-mode temp|pipe] [--outdir DIR]
Exit 0 on success (writes record JSON + transcript + log). Exit 2 on transcribe failure.
"""
import argparse, hashlib, json, os, resource, subprocess, sys, tempfile, time
import numpy as np

def sh_ffmpeg_to_wav(media, tmp):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", media,
           "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", tmp]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg temp extract failed: {r.stderr[-2000:]}")
    return tmp

def sh_ffmpeg_pipe(media):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", media,
           "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"]
    r = subprocess.run(cmd, capture_output=True, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg pipe failed: {r.stderr[-2000:]}")
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0

def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id"); ap.add_argument("media")
    ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    ap.add_argument("--word-ts", action="store_true")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--clip", default="0")
    ap.add_argument("--no-speech-thr", type=float, default=0.6)
    ap.add_argument("--audio-mode", default="temp", choices=["temp", "pipe"])
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    log_path = os.path.join(a.outdir, f"{a.run_id}.log")
    logf = open(log_path, "w")
    def log(*m):
        print(*m, file=logf, flush=True)

    import mlx_whisper
    prompt = None
    if a.prompt:
        with open(a.prompt, encoding="utf-8") as f:
            prompt = f.read()

    t_pre0 = time.time()
    if a.audio_mode == "temp":
        tmp = os.path.join(a.outdir, f"{a.run_id}.wav")
        sh_ffmpeg_to_wav(a.media, tmp)
        audio_in, sr_note = tmp, "16k-mono-wav-temp"
    else:
        audio_in, sr_note = sh_ffmpeg_pipe(a.media), "16k-mono-pipe-numpy"
    t_pre1 = time.time()

    # audio duration via ffprobe
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", a.media],
                        capture_output=True, text=True, timeout=120)
    audio_dur = float(pr.stdout.strip())

    clip = a.clip if a.clip == "0" else [float(x) for x in a.clip.split(",")]
    rss_before = rss_mb()
    t_load0 = time.time()
    # warm: transcribe call includes model load on first call; measure separately via load_model
    from mlx_whisper.transcribe import load_model
    model = load_model(a.model)
    t_load1 = time.time()
    rss_after_load = rss_mb()
    log(f"model={a.model} load_s={t_load1-t_load0:.1f} rss_before={rss_before:.0f}MB rss_after_load={rss_after_load:.0f}MB")

    t_tr0 = time.time()
    try:
        result = mlx_whisper.transcribe(
            audio_in, path_or_hf_repo=a.model, word_timestamps=a.word_ts,
            initial_prompt=prompt, clip_timestamps=clip,
            no_speech_threshold=a.no_speech_thr, verbose=False)
    except Exception as e:
        log(f"TRANSCRIBE_FAILED: {type(e).__name__}: {e}")
        logf.close()
        print(json.dumps({"run_id": a.run_id, "status": "FAIL", "error": f"{type(e).__name__}: {e}"}))
        return 2
    t_tr1 = time.time()
    rss_peak = rss_mb()

    text = result.get("text", "")
    segs = result.get("segments", [])
    tx_path = os.path.join(a.outdir, f"{a.run_id}.txt")
    with open(tx_path, "w", encoding="utf-8") as f:
        f.write(text)
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    words = sum(len(s.get("words", [])) for s in segs) if a.word_ts else None

    rec = {
        "run_id": a.run_id, "status": "OK", "media": a.media,
        "audio_duration_s": round(audio_dur, 2),
        "audio_mode": a.audio_mode, "audio_note": sr_note,
        "model": a.model, "word_timestamps": a.word_ts,
        "prompt_chars": len(prompt) if prompt else 0,
        "clip": a.clip, "no_speech_threshold": a.no_speech_thr,
        "prep_s": round(t_pre1 - t_pre0, 1),
        "model_load_s": round(t_load1 - t_load0, 1),
        "transcribe_s": round(t_tr1 - t_tr0, 1),
        "rtf": round((t_tr1 - t_tr0) / audio_dur, 4) if audio_dur else None,
        "rss_before_mb": round(rss_before, 1),
        "rss_after_load_mb": round(rss_after_load, 1),
        "rss_peak_mb": round(rss_peak, 1),
        "text_chars": len(text), "segments": len(segs),
        "words": words, "text_sha256": h,
        "transcript": tx_path, "log": log_path,
    }
    log(json.dumps(rec, ensure_ascii=False, indent=1))
    logf.close()
    with open(os.path.join(a.outdir, f"{a.run_id}.json"), "w") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(json.dumps(rec, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
