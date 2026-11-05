#!/bin/sh
set -e
python manage.py migrate --noinput
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" 2>/dev/null \
        || echo "superuser $DJANGO_SUPERUSER_USERNAME already exists"
fi
if [ "$LOAD_SAMPLE" = "1" ]; then
    python manage.py load_sample
fi
exec waitress-serve --listen="0.0.0.0:${PORT:-8000}" --threads=8 --channel-timeout=300 oshms.wsgi:application
