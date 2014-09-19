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
    User,
)


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
    LaunchPad().refresh(record)


@celery.task
def parse_tests(rt, results_url, status):
    with transaction.manager:
        rt.url = results_url

        if status == 'FAIL':
            rt.status = 'ERROR'
            DBSession.add(rt)
            return

        rt_json = '%s/json' % rt.url
        response = requests.get(rt_json)
        try:
            response.raise_for_status()
            rt_data = rt_json.json()
        except:
            rt.status = 'UNKNOWN'
            rt_data = None

        if rt_data:
            rt.status = rt_data['result'].upper()

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
            subject = 'Review Queue Test Results'

            if hasattr(item, 'createComment'):
                # It's a merge request
                item.createComment(content=content, vote=vote,
                                   review_type='CBT', subject=subject)
            elif hasattr(item, 'newMessage'):
                # It's a bug
                item.newMessage(content=content, subject=subject)
