#!/bin/bash
python manage.py collectstatic # TODO, to promptuje pytanie are u sure? type yes/no. Trzeba tez chyba dac to do volumena dockerowego?
celery -A website worker -l INFO -P eventlet &
celery -A website worker -l INFO --pool=solo -Q wsQ &
celery -A website beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler &
daphne -b 0.0.0.0 -p 8000 website.asgi:application
wait