import os
import ConfigParser

from datetime import timedelta

from celery import Celery


app_ini = '%s.ini' % os.environ.get('ENV', 'development')

config = ConfigParser.RawConfigParser()
config.read(app_ini)

celery = Celery('reviewq.celery',
                broker=config.get('celery', 'broker'),
                backend=config.get('celery', 'backend'),
                include=['reviewq.tasks'])

# Optional configuration, see the application user guide.
celery.conf.update(
    CELERY_BACKEND_TRANSPORT_OPTIONS=config.get('celery', 'backend_transport_options'),
    CELERY_ACCEPT_CONTENT=['pickle'],
    CELERY_TIMEZONE='UTC',
    CELERYBEAT_SCHEDULE={
        'refresh_active': {
            'task': 'reviewq.tasks.refresh_active',
            'schedule': timedelta(seconds=120),
        },
        'ingest_lp': {
            'task': 'reviewq.tasks.import_from_lp',
            'schedule': timedelta(seconds=600),
        },
    },
    CELERY_ROUTES={
        'reviewq.tasks.parse_tests': {
            'queue': 'priority'
        },
    },
)

if __name__ == '__main__':
    celery.start()
