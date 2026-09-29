#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/snapshot_every_minute.sh SOURCE [OUTPUT_DIR] [INTERVAL_SECONDS]

Examples:
  scripts/snapshot_every_minute.sh sample.mp4
  scripts/snapshot_every_minute.sh /Users/me/Downloads/videos
  scripts/snapshot_every_minute.sh rtsp://user:pass@192.168.1.120/stream media/manual_snapshots 600

Notes:
  - Local video files are processed once, extracting one frame every interval.
  - Directories are scanned for *.mp4 files and processed once.
  - RTSP sources are captured live in a loop every interval until stopped.
  - OUTPUT_DIR defaults to <project>/media/manual_snapshots.
  - INTERVAL_SECONDS defaults to 600, which is 10 minutes.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 1 ]]; then
  usage
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/.." && pwd)"
default_output_dir="$project_root/media/manual_snapshots"

source_video="$1"
output_dir="${2:-$default_output_dir}"
interval_seconds="${3:-600}"

if [[ "$source_video" != rtsp://* && "$source_video" != rtsps://* && ! -e "$source_video" && $# -gt 1 ]]; then
  best_source=""
  best_index=0
  for ((index = 1; index <= $#; index++)); do
    candidate="${*:1:index}"
    if [[ -e "$candidate" ]]; then
      best_source="$candidate"
      best_index="$index"
    fi
  done

  if [[ -n "$best_source" ]]; then
    source_video="$best_source"
    remaining_count=$(($# - best_index))
    if [[ "$remaining_count" -eq 0 ]]; then
      output_dir="$default_output_dir"
      interval_seconds="600"
    elif [[ "$remaining_count" -eq 1 ]]; then
      first_remaining="${@:$((best_index + 1)):1}"
      if [[ "$first_remaining" =~ ^[0-9]+$ ]]; then
        output_dir="$default_output_dir"
        interval_seconds="$first_remaining"
      else
        output_dir="$first_remaining"
        interval_seconds="600"
      fi
    else
      output_dir="${@:$((best_index + 1)):1}"
      interval_seconds="${@:$((best_index + 2)):1}"
    fi
  fi
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required but was not found in PATH." >&2
  exit 1
fi

if ! [[ "$interval_seconds" =~ ^[0-9]+$ ]] || [[ "$interval_seconds" -lt 1 ]]; then
  echo "INTERVAL_SECONDS must be a positive integer." >&2
  exit 1
fi

mkdir -p "$output_dir"

echo "Taking snapshots from: $source_video"
echo "Writing images to: $output_dir"
echo "Interval: ${interval_seconds}s"

safe_name() {
  local name="$1"
  name="${name%.*}"
  printf '%s' "$name" | tr -c '[:alnum:]._-' '_'
}

snapshot_video_file() {
  local video_file="$1"
  local video_output_dir="$2"

  mkdir -p "$video_output_dir"
  echo "Processing video: $video_file"
  echo "Output: $video_output_dir"

  ffmpeg \
    -hide_banner \
    -nostdin \
    -loglevel error \
    -y \
    -i "$video_file" \
    -vf "fps=1/${interval_seconds}" \
    -q:v 2 \
    "$video_output_dir/snapshot-%06d.jpg"
}

if [[ "$source_video" == rtsp://* || "$source_video" == rtsps://* ]]; then
  echo "RTSP mode. Press Ctrl+C to stop."

  while true; do
    timestamp="$(date '+%Y%m%d-%H%M%S')"
    output_path="$output_dir/snapshot-$timestamp.jpg"

    if ffmpeg \
      -hide_banner \
      -nostdin \
      -loglevel error \
      -y \
      -rtsp_transport tcp \
      -i "$source_video" \
      -frames:v 1 \
      -q:v 2 \
      "$output_path"; then
      echo "Saved $output_path"
    else
      echo "Snapshot failed at $timestamp" >&2
      rm -f "$output_path"
    fi

    sleep "$interval_seconds"
  done
elif [[ -d "$source_video" ]]; then
  echo "Directory mode. Finding .mp4 files..."

  found_any=0
  while IFS= read -r -d '' video_file; do
    found_any=1
    video_name="$(safe_name "$(basename "$video_file")")"
    if ! snapshot_video_file "$video_file" "$output_dir/$video_name"; then
      echo "Failed to process $video_file" >&2
    fi
  done < <(find "$source_video" -type f \( -iname '*.mp4' \) -print0 | sort -z)

  if [[ "$found_any" -eq 0 ]]; then
    echo "No .mp4 files found in $source_video" >&2
    exit 1
  fi

  echo "Done. Saved snapshots to $output_dir"
elif [[ -f "$source_video" ]]; then
  echo "Video-file mode. Extracting snapshots from the video timeline..."
  snapshot_video_file "$source_video" "$output_dir"
  echo "Done. Saved snapshots to $output_dir"
else
  echo "SOURCE is not an RTSP URL, file, or directory: $source_video" >&2
  exit 1
fi
