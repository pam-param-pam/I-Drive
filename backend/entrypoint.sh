#!/bin/bash
python manage.py collectstatic --noinput
celery -A website worker -l INFO -P eventlet &
celery -A website worker -l INFO --pool=solo -Q wsQ &
celery -A website worker -l INFO --pool=solo -Q deletion -c 1
celery -A website beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler &
daphne \
  --bind 0.0.0.0 \
  --port 8000 \
  --verbosity 0 \
  --access-log - \
  --proxy-headers \
  website.asgi:application &
wait