#!/usr/bin/env bash
set -euo pipefail

echo "Deploying SmartClass Live Dashboard..."
git add .
git commit -m "Auto-deploy $(date)"
git push origin main

ssh -p 2222 rabah@105.235.135.90 "cd /var/www/smart-classroom-pfe && git pull --ff-only origin main && bash quick_linux_deploy.sh && echo 'LIVE at https://dashboard.rabahdj.online!'"
