#!/usr/bin/env bash
set -euo pipefail

mkdir -p /scripts
cp /motel-stack/init/create_room_db_and_user.sh /scripts/
chmod +x /scripts/create_room_db_and_user.sh

echo "Init scripts copied"
