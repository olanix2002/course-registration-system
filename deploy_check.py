"""Run Django's deployment checks with fake production values.

Every value below is invented for the check only. Nothing here is a real
credential, and the local .env file is not read for these settings.
It also prints the resolved security settings so the values can be seen,
not just the absence of warnings.
"""

import os
import sys

os.environ["SECRET_KEY"] = "fake-deploy-check-key-not-used-anywhere-0000000000"
os.environ["DEBUG"] = "False"
os.environ["RENDER_EXTERNAL_HOSTNAME"] = "courses-example.onrender.com"
os.environ["ALLOWED_HOSTS"] = ""
os.environ["CSRF_TRUSTED_ORIGINS"] = ""
os.environ["INSTITUTION_NAME"] = "SchoolTry"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.conf import settings
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line(["manage.py", "check", "--deploy"])
    print()
    print("Resolved settings with the fake production environment:")
    print(f"  DEBUG={settings.DEBUG}")
    print(f"  ALLOWED_HOSTS={settings.ALLOWED_HOSTS}")
    print(f"  CSRF_TRUSTED_ORIGINS={settings.CSRF_TRUSTED_ORIGINS}")
    print(f"  SECURE_PROXY_SSL_HEADER={settings.SECURE_PROXY_SSL_HEADER}")
    print(f"  SECURE_SSL_REDIRECT={settings.SECURE_SSL_REDIRECT}")
    print(f"  SECURE_HSTS_SECONDS={settings.SECURE_HSTS_SECONDS}")
    print(f"  SESSION_COOKIE_SECURE={settings.SESSION_COOKIE_SECURE}")
    print(f"  CSRF_COOKIE_SECURE={settings.CSRF_COOKIE_SECURE}")
    print(f"  SESSION_COOKIE_NAME={settings.SESSION_COOKIE_NAME}")
    print(f"  STATIC_ROOT={settings.STATIC_ROOT}")
    print(f"  Static storage={settings.STORAGES['staticfiles']['BACKEND']}")
    sys.exit(0)