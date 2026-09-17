#!/bin/bash
set -e

celery -A website worker -l INFO -P prefork -c 2 -n default@%h &
celery -A website worker -l INFO -P prefork -Q cleanup -c 2 -n cleanup@%h &
celery -A website worker -l INFO -P solo -Q deletion -c 1 -n deletion@%h &
celery -A website beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler &
gunicorn \
  -k uvicorn.workers.UvicornWorker \
  -w 4 \
  --bind 0.0.0.0:8000 \
  website.asgi:application
