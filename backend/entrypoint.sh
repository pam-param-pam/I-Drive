daphne website.asgi:application
python3 -m celery -A website worker -l info -P gevent     
celery --app website --broker redis://redis:6379 worker --hostname=ws-worker@%h -l INFO --pool=solo -Q wsQ
celery -A website beat -l DEBUG --scheduler django_celery_beat.schedulers:DatabaseScheduler
