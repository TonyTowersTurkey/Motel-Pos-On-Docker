 # Motel-Pos-On-Docker

 Compose stack and scripts to run `motel-pos` and `Garage_Door_Detection` together.

 ## Quickstart (production)

 1. Copy and edit env files:

 ```bash
 cp motel-stack/.env.example motel-stack/.env
 cp motel-pos/.env.production.example motel-pos/.env.production
 # Edit values and secrets, then secure permissions
 chmod 600 motel-stack/.env motel-pos/.env.production
 ```

 2. Deploy on server:

 ```bash
 cd motel-stack
 ./scripts/deploy.sh
 ```

 3. Smoke test:

 ```bash
 ./scripts/smoke_test_webhook.sh
 ```

 ## Development

 Use the dev compose to mount local source and test hot reload:

 ```bash
 cd motel-stack
 ./scripts/up.sh
 ```

 ## CI

 GitHub Actions validate compose files and run `shellcheck` on scripts.

