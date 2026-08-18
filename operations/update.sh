#!/usr/bin/env bash

# Deploy the latest pushed main commit (or an explicitly supplied full commit SHA)
# to the single-server Penny Saved production host.

set -Eeuo pipefail
umask 027

readonly REPOSITORY_URL="git@github.com:angelah9178/penny-saved.git"
readonly RELEASES_DIR="/srv/penny-saved/releases"
readonly CURRENT_LINK="/srv/penny-saved/current"
readonly ENVIRONMENT_FILE="/etc/penny-saved/backend.env"
readonly SERVICE_NAME="penny-saved"
readonly SERVICE_USER="penny-saved"
readonly DEPLOY_USER="ubuntu"
readonly DEPLOY_HOME="/home/ubuntu"
readonly PRODUCTION_HOST="stopimpulsebuying.online"
readonly BACKUP_DIR="/var/backups/penny-saved"

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
    cat <<'USAGE'
Usage: sudo penny-saved-update [FULL_COMMIT_SHA]

With no argument, deploy the commit currently at origin/main. With an argument,
deploy that exact 40-character lowercase Git commit SHA.
USAGE
    exit 0
fi

if (( $# > 1 )); then
    echo "Usage: sudo penny-saved-update [FULL_COMMIT_SHA]" >&2
    exit 2
fi

if [[ ${EUID} -ne 0 ]]; then
    echo "Run this command with sudo: sudo penny-saved-update" >&2
    exit 1
fi

exec 9>/run/lock/penny-saved-update.lock
if ! flock --nonblock 9; then
    echo "Another Penny Saved update is already running." >&2
    exit 1
fi

for required_path in \
    "$RELEASES_DIR" \
    "$CURRENT_LINK" \
    "$ENVIRONMENT_FILE" \
    "$DEPLOY_HOME/.ssh/penny-saved-github-deploy"; do
    if [[ ! -e $required_path ]]; then
        echo "Required production path is missing: $required_path" >&2
        exit 1
    fi
done

run_as_deployer() {
    runuser --user "$DEPLOY_USER" -- env HOME="$DEPLOY_HOME" "$@"
}

target_commit=${1:-}
if [[ -z $target_commit ]]; then
    target_commit=$(
        run_as_deployer git ls-remote "$REPOSITORY_URL" refs/heads/main |
            awk 'NR == 1 {print $1}'
    )
fi

if [[ ! $target_commit =~ ^[0-9a-f]{40}$ ]]; then
    echo "Expected a full 40-character lowercase Git commit SHA; received: $target_commit" >&2
    exit 1
fi

readonly TARGET_COMMIT=$target_commit
readonly SHORT_COMMIT=${TARGET_COMMIT:0:12}
readonly RELEASE_DIR="$RELEASES_DIR/$TARGET_COMMIT"

if [[ -e $RELEASE_DIR ]]; then
    echo "Release already exists; refusing to overwrite it: $RELEASE_DIR" >&2
    exit 1
fi

old_release=$(readlink --canonicalize-existing "$CURRENT_LINK")
readonly OLD_RELEASE=$old_release

echo "Current release: $OLD_RELEASE"
echo "Target commit:  $TARGET_COMMIT"
echo "New release:    $RELEASE_DIR"

available_percent=$(df --output=pcent "$RELEASES_DIR" | awk 'NR == 2 {gsub(/%/, ""); print 100-$1}')
available_inode_percent=$(df --output=ipcent "$RELEASES_DIR" | awk 'NR == 2 {gsub(/%/, ""); print 100-$1}')
if (( available_percent < 20 || available_inode_percent < 20 )); then
    echo "Deployment stopped: the release filesystem has less than 20% free space or inodes." >&2
    exit 1
fi

echo "Downloading and building the new release..."
run_as_deployer git clone "$REPOSITORY_URL" "$RELEASE_DIR"
run_as_deployer git -C "$RELEASE_DIR" checkout --detach "$TARGET_COMMIT"
[[ $(run_as_deployer git -C "$RELEASE_DIR" rev-parse HEAD) == "$TARGET_COMMIT" ]]

run_as_deployer bash -c '
    set -Eeuo pipefail
    release_dir=$1
    cd "$release_dir"
    source "$HOME/.nvm/nvm.sh"
    nvm install "$(cat .nvmrc)"
    npm --prefix frontend ci
    npm --prefix frontend run build
    python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install --requirement backend/requirements.txt
    .venv/bin/python scripts/check_operations.py
    test -f frontend/dist/index.html
' _ "$RELEASE_DIR"

echo "Validating production configuration with the new release..."
systemd-run --wait --pipe --collect \
    --unit="penny-saved-config-${SHORT_COMMIT}" \
    --uid="$SERVICE_USER" --gid="$SERVICE_USER" \
    --property="WorkingDirectory=$RELEASE_DIR/backend" \
    --property="EnvironmentFile=$ENVIRONMENT_FILE" \
    "$RELEASE_DIR/.venv/bin/python" \
    -c 'from app.main import create_app; create_app(); print("configuration valid")'

echo "Creating the pre-migration PostgreSQL backup..."
backup_timestamp=$(date --utc +%Y%m%dT%H%M%SZ)
readonly BACKUP_FILE="$BACKUP_DIR/penny_saved_${backup_timestamp}_${SHORT_COMMIT}.dump"
runuser --user postgres -- pg_dump --dbname=penny_saved --format=custom \
    --no-owner --no-acl --file="$BACKUP_FILE"
runuser --user postgres -- pg_restore --list "$BACKUP_FILE" >/dev/null
sha256sum "$BACKUP_FILE" | tee "$BACKUP_FILE.sha256"
chmod 0640 "$BACKUP_FILE.sha256"

echo "Applying database migrations..."
systemd-run --wait --pipe --collect \
    --unit="penny-saved-migrate-${SHORT_COMMIT}" \
    --uid="$SERVICE_USER" --gid="$SERVICE_USER" \
    --property="WorkingDirectory=$RELEASE_DIR/backend" \
    --property="EnvironmentFile=$ENVIRONMENT_FILE" \
    "$RELEASE_DIR/.venv/bin/python" -m alembic upgrade head
systemd-run --wait --pipe --collect \
    --unit="penny-saved-migration-status-${SHORT_COMMIT}" \
    --uid="$SERVICE_USER" --gid="$SERVICE_USER" \
    --property="WorkingDirectory=$RELEASE_DIR/backend" \
    --property="EnvironmentFile=$ENVIRONMENT_FILE" \
    "$RELEASE_DIR/.venv/bin/python" -m alembic current

if [[ -e $CURRENT_LINK.next ]]; then
    echo "Activation path already exists; inspect it before retrying: $CURRENT_LINK.next" >&2
    exit 1
fi

echo "Activating the new release..."
ln --symbolic "$RELEASE_DIR" "$CURRENT_LINK.next"
mv -T "$CURRENT_LINK.next" "$CURRENT_LINK"
systemctl restart "$SERVICE_NAME"

if ! timeout 30 bash -c \
    'until curl --fail --silent --header "Host: stopimpulsebuying.online" http://127.0.0.1:8000/api/health >/dev/null; do sleep 1; done'; then
    echo "The new release did not become healthy." >&2
    echo "Previous release: $OLD_RELEASE" >&2
    echo "Database rollback is not automatic. Inspect: journalctl -u $SERVICE_NAME -n 100" >&2
    exit 1
fi

curl --fail --silent --show-error --header "Host: $PRODUCTION_HOST" \
    http://127.0.0.1:8000/api/ready >/dev/null
curl --fail --silent --show-error \
    "https://$PRODUCTION_HOST/api/health" >/dev/null
curl --fail --silent --show-error \
    "https://$PRODUCTION_HOST/api/ready" >/dev/null

echo "Deployment succeeded."
echo "Active commit:   $TARGET_COMMIT"
echo "Previous release: $OLD_RELEASE"
echo "Backup:          $BACKUP_FILE"
echo "Test the changed behavior at https://$PRODUCTION_HOST before closing SSH."
