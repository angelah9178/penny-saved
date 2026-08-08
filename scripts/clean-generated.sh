#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repository_root=$(cd -- "$script_dir/.." && pwd -P)

if [[ -z "$repository_root" || "$repository_root" == "/" ]]; then
  echo "Refusing cleanup: invalid repository root." >&2
  exit 1
fi

required_paths=(
  "$repository_root/Makefile"
  "$repository_root/backend"
  "$repository_root/frontend"
  "$repository_root/scripts/clean-generated.sh"
)

for required_path in "${required_paths[@]}"; do
  if [[ ! -e "$required_path" ]]; then
    echo "Refusing cleanup: expected repository path is missing: $required_path" >&2
    exit 1
  fi
done

generated_directories=(
  "$repository_root/frontend/dist"
  "$repository_root/frontend/coverage"
  "$repository_root/frontend/test-results"
  "$repository_root/frontend/playwright-report"
  "$repository_root/frontend/blob-report"
  "$repository_root/frontend/e2e-artifacts"
  "$repository_root/backend/.pytest_cache"
  "$repository_root/backend/.ruff_cache"
  "$repository_root/backend/htmlcov"
)

generated_files=(
  "$repository_root/backend/.coverage"
  "$repository_root/frontend/.coverage"
  "$repository_root/frontend/tsconfig.app.tsbuildinfo"
  "$repository_root/frontend/tsconfig.node.tsbuildinfo"
)

for generated_directory in "${generated_directories[@]}"; do
  rm -rf -- "$generated_directory"
done

for generated_file in "${generated_files[@]}"; do
  rm -f -- "$generated_file"
done

python_roots=(
  "$repository_root/backend/alembic"
  "$repository_root/backend/app"
  "$repository_root/backend/tests"
)

for python_root in "${python_roots[@]}"; do
  [[ -d "$python_root" ]] || continue
  find "$python_root" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
  find "$python_root" -depth -type d -name '__pycache__' -exec rm -rf -- {} +
done
