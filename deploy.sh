#!/bin/bash
echo "🚀 Deploying SmartHelmet Live Dashboard..."
git add .
git commit -m "Auto-deploy $(date)"
git push origin main
ssh -p 2222 rabah@105.235.135.90 "cd /var/www/smart-helmet-pfe && git pull origin main && cd /var/www/smart-helmet-pfe && python manage.py migrate && sudo systemctl restart smarthelmet-django.service && echo '✅ LIVE at https://dashboard.rabahdj.online!'"
