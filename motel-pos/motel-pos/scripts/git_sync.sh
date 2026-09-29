#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir/.." rev-parse --show-toplevel)"
cd "$repo_root"

ssh_key="${SSH_KEY:-/home/openclaw/.ssh/openclaw_motelpos_ed25519}"
server_host="${SERVER_HOST:-root@motel-pos.coral}"
server_repo="${SERVER_REPO:-/srv/django/myproject}"
server_remote_bare="${SERVER_REMOTE_BARE:-/srv/django/myproject.git}"
remote_name="${REMOTE_NAME:-origin}"
branch="${BRANCH:-$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)}"
commit_message=""
dry_run=0

usage() {
  cat <<'EOF'
Usage: scripts/git_sync.sh [options]

Commit local changes if present, push to the bare remote, and pull on the
server checkout over SSH.

Options:
  -m, --message TEXT        Commit message to use when local changes exist.
  --branch NAME             Branch to sync. Defaults to the current branch.
  --server-host HOST        SSH target for the server. Default: root@motel-pos.coral
  --server-repo PATH        Server checkout path. Default: /srv/django/myproject
  --server-remote-bare PATH Bare repo path on the server. Default: /srv/django/myproject.git
  --ssh-key PATH            SSH private key to use. Default: /home/openclaw/.ssh/openclaw_motelpos_ed25519
  --remote-name NAME        Git remote name to push/pull. Default: origin
  --dry-run                 Print the actions without changing anything.
  -h, --help                Show this help.
EOF
}

log() {
  printf '%s\n' "$*"
}

run_cmd() {
  if [[ "$dry_run" -eq 1 ]]; then
    printf '[dry-run]'
    for arg in "$@"; do
      printf ' %q' "$arg"
    done
    printf '\n'
    return 0
  fi
  "$@"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--message)
      [[ $# -ge 2 ]] || { log "Missing value for $1"; exit 2; }
      commit_message="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || { log "Missing value for $1"; exit 2; }
      branch="$2"
      shift 2
      ;;
    --server-host)
      [[ $# -ge 2 ]] || { log "Missing value for $1"; exit 2; }
      server_host="$2"
      shift 2
      ;;
    --server-repo)
      [[ $# -ge 2 ]] || { log "Missing value for $1"; exit 2; }
      server_repo="$2"
      shift 2
      ;;
    --server-remote-bare)
      [[ $# -ge 2 ]] || { log "Missing value for $1"; exit 2; }
      server_remote_bare="$2"
      shift 2
      ;;
    --ssh-key)
      [[ $# -ge 2 ]] || { log "Missing value for $1"; exit 2; }
      ssh_key="$2"
      shift 2
      ;;
    --remote-name)
      [[ $# -ge 2 ]] || { log "Missing value for $1"; exit 2; }
      remote_name="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log "Unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$branch" ]]; then
  log "Unable to determine the current branch. Pass --branch explicitly."
  exit 2
fi

export GIT_SSH_COMMAND="ssh -i $ssh_key -o IdentitiesOnly=yes -o BatchMode=yes"

log "Repo: $repo_root"
log "Branch: $branch"
log "Remote: $remote_name"
log "Server: $server_host"
log "Server repo: $server_repo"
log "Bare remote: $server_remote_bare"

local_status="$(git status --porcelain=v1)"
if [[ -n "$local_status" ]]; then
  log "Local working tree has changes."
  run_cmd git add -A
  if ! git diff --cached --quiet --exit-code; then
    if [[ -z "$commit_message" ]]; then
      commit_message="sync: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    fi
    run_cmd git commit -m "$commit_message"
  else
    log "Nothing staged after add; skipping commit."
  fi
else
  log "Local working tree is clean."
fi

run_cmd git push "$remote_name" "$branch"

if [[ "$dry_run" -eq 1 ]]; then
  printf '[dry-run] ssh -i %q -o IdentitiesOnly=yes -o BatchMode=yes %q %q\n' \
    "$ssh_key" \
    "$server_host" \
    "cd $server_repo && ..."
  exit 0
fi

ssh -i "$ssh_key" -o IdentitiesOnly=yes -o BatchMode=yes "$server_host" \
  "SERVER_REPO=$(printf '%q' "$server_repo") SERVER_REMOTE_BARE=$(printf '%q' "$server_remote_bare") REMOTE_NAME=$(printf '%q' "$remote_name") BRANCH=$(printf '%q' "$branch") bash -se" <<'REMOTE'
set -euo pipefail

cd "$SERVER_REPO"

if ! git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
  git remote add "$REMOTE_NAME" "$SERVER_REMOTE_BARE"
else
  git remote set-url "$REMOTE_NAME" "$SERVER_REMOTE_BARE"
fi

if [[ -n "$(git status --porcelain=v1)" ]]; then
  stash_msg="sync-script $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git stash push --include-untracked --message "$stash_msg" >/dev/null
  echo "Stashed existing server worktree state: $stash_msg"
fi

git fetch "$REMOTE_NAME" "$BRANCH"
git pull --ff-only "$REMOTE_NAME" "$BRANCH"

echo "Server HEAD: $(git rev-parse --short HEAD)"
echo "Server status:"
git status --short
REMOTE

log "Local HEAD: $(git rev-parse --short HEAD)"
log "Local status:"
git status --short
