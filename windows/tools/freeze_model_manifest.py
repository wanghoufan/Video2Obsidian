#!/usr/bin/env python3
"""在**联网机**上冻结 CT2 模型并生成/更新模型清单（windows/models/MODEL_MANIFEST.json）。

用法（Windows，联网机，venv 里）：

    .\\.venv\\Scripts\\python.exe tools\\freeze_model_manifest.py ^
        --model-dir D:\\models\\faster-whisper-large-v3-turbo ^
        --revision <CT2 checkpoint 的 commit> ^
        --source https://huggingface.co/Systran/faster-whisper-large-v3-turbo ^
        --license MIT --license-file LICENSE

它做三件事，**不多做**：① 逐个文件算 SHA-256 与字节数；② 把
来源/revision/许可/绝对路径写进清单；③ 打印可人工核对的摘要。

它**不做**：不联网下载模型（模型目录必须先由人工备好）、不改写既有的其他
登记项以外的东西、不猜 revision（空着即报错退出）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from asr_backend.manifest import (  # noqa: E402
    MANIFEST_BASENAME,
    REVISION_RE,
    SCHEMA,
)

PLACEHOLDERS = ("replace", "todo", "fixme", "unknown", "REPLACE")


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def collect_files(model_dir: str) -> list:
    files = []
    for name in sorted(os.listdir(model_dir)):
        full = os.path.join(model_dir, name)
        if not os.path.isfile(full):
            continue
        if name == MANIFEST_BASENAME:
            continue
        files.append({
            "path": name,
            "sha256": sha256_file(full),
            "bytes": os.path.getsize(full),
        })
    return files


def is_placeholder(value: str) -> bool:
    low = str(value or "").strip().lower()
    return low == "" or any(mark in low for mark in PLACEHOLDERS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="冻结 CT2 模型并生成清单")
    parser.add_argument("--model-dir", required=True, help="模型目录（绝对路径）")
    parser.add_argument("--revision", required=True, help="CT2 checkpoint 的 revision")
    parser.add_argument("--source", required=True, help="来源 URL 或发布资产名")
    parser.add_argument("--license", required=True, help="许可")
    parser.add_argument("--license-file", default="LICENSE", help="许可文件名")
    parser.add_argument("--model-id", default="Systran/faster-whisper-large-v3-turbo")
    parser.add_argument("--compute-type", default="int8_float16")
    parser.add_argument("--manifest", default=os.path.join(ROOT, "models",
                                                           MANIFEST_BASENAME))
    args = parser.parse_args(argv)

    model_dir = os.path.abspath(args.model_dir)
    if not os.path.isdir(model_dir):
        print("模型目录不存在或不是目录：%s" % (model_dir,), file=sys.stderr)
        return 2
    if not os.path.isabs(model_dir):
        print("模型目录必须是绝对路径（交付机按绝对路径加载）：%s"
              % (model_dir,), file=sys.stderr)
        return 2
    revision = str(args.revision).strip().lower()
    if not REVISION_RE.match(revision) or is_placeholder(revision):
        print("revision 必须冻结成真实 commit（不许留占位）：%r" % (args.revision,),
              file=sys.stderr)
        return 2
    for label, value in (("--source", args.source), ("--license", args.license)):
        if is_placeholder(value):
            print("%s 不许留占位：%r" % (label, value), file=sys.stderr)
            return 2

    files = collect_files(model_dir)
    if not files:
        print("模型目录里没有任何文件，拒绝生成空清单：%s" % (model_dir,),
              file=sys.stderr)
        return 2

    entry = {
        "model_id": args.model_id,
        "source": args.source.strip(),
        "revision": revision,
        "license": args.license.strip(),
        "license_file": args.license_file,
        "local_path": model_dir,
        "compute_type": args.compute_type,
        "files": files,
    }

    payload = {"schema": SCHEMA, "models": [entry]}
    os.makedirs(os.path.dirname(os.path.abspath(args.manifest)), exist_ok=True)
    with open(args.manifest, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    total = sum(item["bytes"] for item in files)
    print("已写清单：%s" % (os.path.abspath(args.manifest),))
    print("模型：%s @ %s（%s）" % (entry["model_id"], entry["revision"],
                                 entry["license"]))
    print("来源：%s" % (entry["source"],))
    print("文件 %d 个，共 %.1f MiB" % (len(files), total / 1048576.0))
    for item in files:
        print("  %-24s %10d B  %s" % (item["path"], item["bytes"], item["sha256"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
