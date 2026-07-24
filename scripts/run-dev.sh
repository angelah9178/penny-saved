#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repository_root=$(cd -- "$script_dir/.." && pwd -P)

if [[ -z "$repository_root" || "$repository_root" == "/" || ! -f "$repository_root/Makefile" ]]; then
  echo "Refusing development startup: invalid repository root." >&2
  exit 1
fi

command -v make >/dev/null || {
  echo "GNU Make is required." >&2
  exit 1
}
command -v setsid >/dev/null || {
  echo "The 'setsid' command is required for development process supervision." >&2
  exit 1
}

backend_pid=
frontend_pid=

terminate_process_group() {
  local process_id=$1

  if [[ -n "$process_id" ]] && kill -0 "$process_id" 2>/dev/null; then
    kill -TERM -- "-$process_id" 2>/dev/null || true
  fi
}

reap_child() {
  local process_id=$1

  if [[ -n "$process_id" ]]; then
    wait "$process_id" 2>/dev/null || true
  fi
}

shutdown_children() {
  trap - INT TERM
  terminate_process_group "$backend_pid"
  terminate_process_group "$frontend_pid"
  reap_child "$backend_pid"
  reap_child "$frontend_pid"
}

handle_signal() {
  local exit_status=$1

  shutdown_children
  exit "$exit_status"
}

trap 'handle_signal 130' INT
trap 'handle_signal 143' TERM

setsid make --no-print-directory --directory="$repository_root" backend-dev &
backend_pid=$!
setsid make --no-print-directory --directory="$repository_root" frontend-dev &
frontend_pid=$!

set +e
wait -n "$backend_pid" "$frontend_pid"
first_exit_status=$?
set -e

shutdown_children
exit "$first_exit_status"
