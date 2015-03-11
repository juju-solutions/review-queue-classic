import requests
import transaction

from celerycfg import celery
from celery.signals import worker_init

from .plugins.launchpad import LaunchPad
from launchpadlib import errors

from .helpers import (
    get_lp,
)

from .models import (
    DBSession,
    Base,
    Review,
)


@celery.task
def import_from_lp():
    LaunchPad().ingest('charmers')


@worker_init.connect
def bootstrap_pyramid(signal, sender):
    import os
    from pyramid.paster import bootstrap, get_appsettings
    from sqlalchemy import engine_from_config

    sender.app.settings = bootstrap('%s.ini' %
                                    os.environ.get('ENV', 'development'))['registry'].settings
    settings = get_appsettings('%s.ini' %
                               os.environ.get('ENV', 'development'),
                               options={})

    engine = engine_from_config(settings, 'sqlalchemy.')

    DBSession.configure(bind=engine)
    Base.metadata.bind = engine


@celery.task
def refresh(record):
    from celery.utils.log import get_task_logger
    LaunchPad().refresh(record)


@celery.task
def refresh_active():
    active = (DBSession.query(Review)
                       .filter(Review.state.in_(['REVIEWED',
                                                 'PENDING',
                                                 'IN PROGRESS',
                                                 'FOLLOW UP',
                                                 'READY',
                                                 'NEW']))).all()
    for a in active:
        refresh.delay(a)


@celery.task(bind=True)
def parse_tests(self, rt, results_url):
    with transaction.manager:
        rt.url = results_url

        rt_json = '%s/json' % results_url
        try:
            response = requests.get(rt_json, timeout=30)
            response.raise_for_status()
            rt_data = response.json()
        except Exception as e:
            DBSession.add(rt)
            self.retry(exc=e, countdown=300)

        if rt_data:
            rt.status = rt_data['result'].upper()

        DBSession.add(rt)

        lp = get_lp(True)

        try:
            lp.me
        except errors.Unauthorized:
            return

        item = lp.load(rt.review.api_url)
        content = None
        if rt.status == 'FAIL':
            vote = 'Needs Fixing'
            content = ('This items has failed automated testing! '
                       'Results available here %s' % rt.url)
        elif rt.status == 'PASS':
            vote = 'Approve'
            content = ('The results (%s) are in and available here: %s' %
                       (rt.status, rt.url))

        if content:
            subject = 'Automated Test Results: %s' % rt.review.title

            if hasattr(item, 'createComment'):
                # It's a merge request
                item.createComment(content=content, vote=vote,
                                   review_type='Automated Testing',
                                   subject=subject)
            elif hasattr(item, 'bug'):
                # It's a bug
                item.bug.newMessage(content=content, subject=subject)
