#!/bin/sh
# 懒得笔记 本机控制台一键启动：选 python -> 起 127.0.0.1:8899（V2O_PORT 可覆盖）-> 打开浏览器。
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# P1-8：端口收敛到这一处；真源＝app/server.py 的 PORT 默认值（8899），V2O_PORT 优先。
PORT="${V2O_PORT:-8899}"

PY=""
for cand in "$ROOT/stage0bench/bin/python" "$ROOT/.venv/bin/python" "$ROOT/venv/bin/python"; do
  if [ -x "$cand" ]; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  PY="python3"
  echo "WARN: 未找到 stage0bench/.venv/venv，转写需要 faster-whisper/CT2 的 python；先用 $PY 起控制台（/api/start 会 400 提示换 venv）。"
else
  echo "venv 复核：$PY"
  "$PY" -c "import sys; print('复核 python：' + sys.executable)"
fi

# P0-6：转写必须在有 faster-whisper/CT2 的 python 下跑；缺则只告警（控制台仍可起，/api/start 会 400 明确提示）。
if "$PY" -c "import faster_whisper, ctranslate2" 2>/dev/null; then
  echo "faster-whisper/CT2 就绪，转写可用。"
else
  echo "WARN: $PY 缺 faster_whisper/ctranslate2，转写 /api/start 会 400（PRECHECK_ASR_BACKEND_MISSING）；请按 requirements.txt 装好后重起。" >&2
fi

echo "用 $PY 启动 懒得笔记 本机控制台…"
V2O_PORT="$PORT" "$PY" app/server.py &
SRV=$!
sleep 1
if ! kill -0 $SRV 2>/dev/null; then
  echo "启动失败，查看上方报错。" >&2
  exit 1
fi
echo "已起 http://127.0.0.1:$PORT/（Ctrl+C 停止）"
if command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:$PORT/"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:$PORT/"
fi
wait $SRV
