#!/usr/bin/env bash
# Build script for Render. Every step is safe to run again: pip skips
# requirements that are already installed, collectstatic and migrate are
# idempotent, and create_admin and seed_data look before they write.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Create or update the staff account from ADMIN_USERNAME and ADMIN_PASSWORD.
python manage.py create_admin

# Insert the sample courses, students and registrations, skipping existing rows.
python manage.py seed_data