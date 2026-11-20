#!/usr/bin/env bash
# Render build: install, collect static files, migrate (also seeds the fault library), demo data.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
if [ -n "${DEMO_PASSWORD:-}" ]; then python manage.py seed_demo --password "$DEMO_PASSWORD"; fi
