from celerycfg import celery
from celery.signals import worker_init

from launchpadlib import errors
from pyramid.settings import asbool

from .plugins.launchpad import LaunchPad
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
    LaunchPad(celery.settings).ingest('charmers')


@worker_init.connect
def bootstrap_pyramid(signal, sender):
    import os
    from pyramid.paster import bootstrap, get_appsettings
    from sqlalchemy import engine_from_config

    sender.app.settings = bootstrap(
        '%s.ini' % os.environ.get('ENV', 'development'))['registry'].settings
    settings = get_appsettings('%s.ini' %
                               os.environ.get('ENV', 'development'),
                               options={})

    engine = engine_from_config(settings, 'sqlalchemy.')

    DBSession.configure(bind=engine)
    Base.metadata.bind = engine


@celery.task
def refresh(record):
    LaunchPad(celery.settings).refresh(record)


@celery.task
def refresh_active():
    active = (
        DBSession.query(Review)
        .filter(Review.state.in_([
            'REVIEWED',
            'PENDING',
            'IN PROGRESS',
            'FOLLOW UP',
            'READY',
            'NEW'
        ]))
    )
    for a in active:
        refresh.delay(a)


@celery.task(bind=True)
def update_lp_item(self, rt):
    """Update launchpad item (bug or merge proposal) with
    results of a test run (single substrate).

    """
    lp = get_lp(True)
    try:
        lp.me
    except errors.Unauthorized:
        return

    DBSession.add(rt)
    item = lp.load(rt.review.api_url)
    content = None
    if rt.status == 'FAIL':
        vote = 'Needs Fixing'
        content = (
            'This item has failed automated testing! '
            'Results available here %s' % rt.url)
    elif rt.status == 'PASS':
        vote = 'Approve'
        content = (
            'The results (%s) are in and available here: %s' %
            (rt.status, rt.url))

    if content and asbool(celery.settings.get('testing.comments')):
        subject = (
            '%s Test Results: %s' % (
                (rt.substrate or '').upper(),
                rt.review.title))

        if hasattr(item, 'createComment'):
            # It's a merge request
            item.createComment(
                content=content, vote=vote,
                review_type='Automated Testing',
                subject=subject)
        elif hasattr(item, 'bug'):
            # It's a bug
            item.bug.newMessage(
                content=content, subject=subject)
