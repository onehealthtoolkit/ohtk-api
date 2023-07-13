#!/bin/bash

# Collect static files
echo "Collect static files"
python manage.py collectstatic --noinput

# Apply database migrations
echo "Apply database migrations"
python manage.py migrate

# Create django superuser
if [ -z "$DJANGO_SUPERUSER_USERNAME" ] || [ -z "$DJANGO_SUPERUSER_PASSWORD" ] || [ -z "$DJANGO_SUPERUSER_EMAIL" ]
then
    echo "No superuser created"
else
    echo "Creating superuser"
    python manage.py createsuperuser --noinput \
        --username $DJANGO_SUPERUSER_USERNAME \
        --email $DJANGO_SUPERUSER_EMAIL
fi

# Start server
echo "Starting server"
python manage.py runserver 0.0.0.0:8000