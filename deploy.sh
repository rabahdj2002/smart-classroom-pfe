#!/bin/bash
echo "🚀 Deploying SmartClass Live Dashboard..."
git add .
git commit -m "Auto-deploy $(date)"
git push origin main
ssh -p 2222 rabah@105.235.135.90 "cd /var/www/smart-classroom-pfe && git pull origin main && cd /var/www/smart-classroom-pfe && python manage.py migrate && sudo systemctl restart smartclass-django.service && echo '✅ LIVE at https://dashboard.rabahdj.online!'"
