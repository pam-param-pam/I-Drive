#!/bin/bash
python manage.py collectstatic # TODO, to promptuje pytanie are u sure? type yes/no. Trzeba tez chyba dac to do volumena dockerowego?
python manage.py makemigrations website
python manage.py migrate
daphne -b 0.0.0.0 -p 8000 website.asgi:application &
python3 -m celery -A website worker -l INFO -P gevent &
celery -A website --broker redis://redis:6379 worker --hostname=ws-worker@%h -l INFO --pool=solo -Q wsQ &
celery -A website beat -l DEBUG --scheduler django_celery_beat.schedulers:DatabaseScheduler
