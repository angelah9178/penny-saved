#!/usr/bin/env bash
set -euo pipefail

action=${1:-database operation}
environment_file=${2:-backend/.env}

if [[ ! -f "$environment_file" ]]; then
  echo "Missing $environment_file. Run 'make env-setup' and review its values." >&2
  exit 1
fi

read_setting() {
  local key=$1
  local value

  value=$(sed -n "s/^${key}=//p" "$environment_file" | tail -n 1)
  value=${value%$'\r'}
  value=${value#\"}
  value=${value%\"}
  value=${value#\'}
  value=${value%\'}
  printf '%s' "$value"
}

app_env=$(read_setting APP_ENV)
database_url=$(read_setting DATABASE_URL)

if [[ "$app_env" != "development" ]]; then
  echo "Refusing $action: APP_ENV must be development, found '${app_env:-unset}'." >&2
  exit 1
fi

if [[ -z "$database_url" ]]; then
  echo "Refusing $action: DATABASE_URL is missing from $environment_file." >&2
  exit 1
fi

database_authority=${database_url#*://}
database_authority=${database_authority#*@}
database_authority=${database_authority%%/*}

if [[ "$database_authority" == \[* ]]; then
  database_host=${database_authority#\[}
  database_host=${database_host%%\]*}
else
  database_host=${database_authority%%:*}
fi

case "$database_host" in
  localhost | 127.0.0.1 | ::1) ;;
  *)
    echo "Refusing $action: database host '$database_host' is not local." >&2
    exit 1
    ;;
esac
