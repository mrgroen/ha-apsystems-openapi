#!/bin/bash
# /home/user/scripts/apsys_check.sh
# call from crontab:
# 0 10 * * * /home/user/scripts/apsys_check.sh >> /home/user/logs/apsys_health.log 2>&1

export APSYS_EMAIL_TO="your-email@example.com"
export APSYS_SMTP_HOST="smtp.gmail.com"
export APSYS_SMTP_PORT="587"
export APSYS_SMTP_TLS="true"
export APSYS_SMTP_USER="sender@gmail.com"
export APSYS_SMTP_PASS="your-app-password"
export APSYS_EMAIL_FROM="sender@gmail.com"

/usr/bin/python3 /home/user/apsys_health.py \
  --app-id "$APSYS_APP_ID" \
  --app-secret "$APSYS_APP_SECRET" \
  --sid "$APSYS_SID" \
  --single-panel-uids 703000433609 \
  --quiet --alert-only