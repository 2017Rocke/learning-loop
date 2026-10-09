#!/bin/zsh
set -eu
LEARNING_ROOT="${0:A:h}"
cd "$LEARNING_ROOT"
mkdir -p data
if ! curl --silent --fail --max-time 2 http://127.0.0.1:8765/api/state >/dev/null; then
  nohup python3 -B learning_loop.py serve --port 8765 >data/server.log 2>&1 </dev/null &
  echo $! >data/server.pid
  for attempt in {1..30}; do
    if curl --silent --fail --max-time 1 http://127.0.0.1:8765/api/state >/dev/null; then
      break
    fi
    sleep 0.2
  done
fi
if curl --silent --fail --max-time 2 http://127.0.0.1:8765/api/state >/dev/null; then
  open http://127.0.0.1:8765/
else
  print '启动失败，请查看项目 data/server.log，或让 Codex 检查。'
  exit 1
fi
