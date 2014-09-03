import re
import time
import transaction

from .models import (
    DBSession,
    Source,
    Review,
    Profile,
    User,
    ReviewVote,

from .helpers import (
    get_lp,
    wait_a_second,
)

from sqlalchemy import engine_from_config
from sqlalchemy import orm

from pyramid.paster import (
    get_appsettings,
    setup_logging,
)


settings = get_appsettings('development.ini', options={})
engine = engine_from_config(settings, 'sqlalchemy.')
DBSession.configure(bind=engine)
charmers = get_lp().people['charmers']


def import_from_lp():
    get_bugs()
    get_merges()


def get_merges():
    #proposals = charmers.getRequestedReviews()
    b = charmers.getBranches()

    for branch in b:
        m = branch.getMergeProposals(status=['Work in progress',
                                             'Needs review', 'Approved',
                                             'Rejected', 'Merged',
                                             'Code failed to merge', 'Queued',
                                             'Superseded'])
        for merge in m:
            create_review_from_merge(merge)


def get_bugs():
    lp = get_lp()
    charm = lp.distributions['charms']
    branch_filter = "Show only Bugs with linked Branches"
    bugs = charm.searchTasks(linked_branches=branch_filter)
    for bug in bugs:
        if '+source' in bug.web_link:
            continue
        create_review_from_bug(bug,
                               lp.bugs[int(''.join(bug.web_link.split('/')[-1:]))])


def bug_state(bug_task):
    if not bug_task.date_left_new and bug_task.status == 'New':
        return 'NEW'

    return map_lp_state(bug_task.status)


def map_lp_state(state):
    # 'NEW', 'PENDING', 'REVIEWED', 'MERGED', 'CLOSED', 'READY', 'ABANDONDED',
    # 'IN PROGRESS', 'FOLLOW UP'
    states = {'new': 'PENDING',
              'incomplete': 'REVIEWED',
              'opinion': 'CLOSED',
              'invalid': 'CLOSED',
              "won't fix": 'ABANDONDED',
              'confirmed': 'PENDING',
              'triaged': 'PENDING',
              'in progress': 'IN PROGRESS',
              'fix committed': 'READY',
              'fix released': 'CLOSED',
              'needs review': 'PENDING',
              'work in progress': 'IN PROGRESS',
              'approved': 'READY',
              'rejected': 'ABANDONDED',
              'merged': 'MERGED',
              'superseded': 'ABANDONDED',
              'queued': 'PENDING',
              'code failed to merge': 'FOLLOW UP',
             }

    return states[state.lower()]


def create_series(series):
    try:
        s = DBSession.query(Series).filter_by(slug=series.lower()).one()
    except orm.exc.NoResultFound:
        pass
    else:
        return s

    with transaction.manager:
        s = Series(slug=series.lower(), name=series)
        DBSession.add(s)

    return DBSession.query(Series).filter_by(slug=series.lower()).one()


def create_project(name):
    try:
        p = DBSession.query(Project).filter_by(name=name.lower()).one()
    except orm.exc.NoResultFound:
        pass
    else:
        return p

    with transaction.manager:
        p = Project(name=name.lower())
        DBSession.add(p)

    return create_project(name)


@wait_a_second
def create_review_from_merge(task):
    with transaction.manager:
        r = DBSession.query(Review).filter_by(api_url=task.self_link).first()

        if not r:
            r = Review(type='UPDATE', api_url=task.self_link,
                       created=task.date_created.replace(tzinfo=None))

        print(task)
        title = "%s into %s" % (task.source_branch.display_name,
                                task.target_branch.display_name)
        r.url = task.web_link
        r.title = title=title
        r.state = map_lp_state(task.queue_status)
        r.owner = create_user(task.registrant)
        r.source = DBSession.query(Source).filter_by(slug='lp').one()
        comments = task.all_comments

        if len(comments) > 0:
            r.updated = comments[len(comments)-1].date_created.replace(tzinfo=None)
        else:
            r.updated = task.date_created.replace(tzinfo=None)

        if r.state in ['REVIEWED', 'CLOSED'] and len(comments) > 0:
            if comments[len(comments)-1].author == task.registrant:
                r.state = 'FOLLOW UP'

        DBSession.add(r)

    parse_comments(comments, r)


@wait_a_second
def create_review_from_bug(task, bug):
    with transaction.manager:
        r = DBSession.query(Review).filter_by(api_url=task.self_link).first()

        if not r:
            r = Review(type='NEW', api_url=task.self_link,
                       created=task.date_created.replace(tzinfo=None))

        print(bug)
        r.title = bug.title
        r.url = task.web_link
        r.state = bug_state(task)
        r.updated = bug.date_last_message.replace(tzinfo=None) if bug.date_last_message > bug.date_last_updated else bug.date_last_updated.replace(tzinfo=None)
        r.owner = create_user(task.owner)
        r.source = DBSession.query(Source).filter_by(slug='lp').one()

        if r.state in ['REVIEWED', 'CLOSED']:
            if bug.messages[len(bug.messages)-1].owner == task.assignee:
                r.state = 'FOLLOW UP'

        DBSession.add(r)

    parse_messages(bug.messages, r)


def parse_comments(comments, review):
    for m in comments:
        try:
            DBSession.query(ReviewVote).filter_by(comment_id=m.self_link).one()
        except orm.exc.NoResultFound:
            pass
        else:
            print(m.self_link)
            continue

        with transaction.manager:
            s = determine_sentiment(m.vote)
            u = create_user(m.author)
            v = ReviewVote(vote=s, comment_id=m.self_link, created=m.date_created.replace(tzinfo=None))
            print("Inserting %s (%s) %s" % (m.self_link, s, u.name))
            v.owner = u
            v.review = review
            DBSession.add(v)


def parse_messages(comments, review):
    first = True  # Hate this
    for m in comments:
        if first:
            first = False
            continue

        try:
            DBSession.query(ReviewVote).filter_by(comment_id=m.self_link).one()
        except orm.exc.NoResultFound:
            pass
        else:
            print(m.self_link)
            continue

        with transaction.manager:
            s = determine_sentiment(m.content)
            u = create_user(m.owner)
            v = ReviewVote(vote=s, comment_id=m.self_link)
            print("Inserting %s (%s) %s" % (m.self_link, s, u.name))
            v.owner = u
            v.review = review
            DBSession.add(v)


def create_user(profile):
    p = DBSession.query(Profile).filter_by(url=profile.web_link).first()

    if p:
        return p.user

    with transaction.manager:
        # It's an LP profile
        p = Profile(name=profile.display_name, username=profile.name,
                    url=profile.web_link)
        p.source = DBSession.query(Source).filter_by(slug='lp').first()

        r = User(name=profile.display_name,
                 is_charmer=profile in charmers.members)
        p.user = r
        DBSession.add(r)
        DBSession.add(p)

    return DBSession.query(Profile).filter_by(url=profile.web_link).first().user


def determine_sentiment(text):
    if not text:
        return 'COMMENT'

    positive = ['lgtm', '\+1', 'approve']
    negative = ['nlgtm', '\-1 ', 'needs work', 'needs fixing',
                'needs information', 'disapprove', 'resubmit', 'dnlgtm']
    sentiment = 0
    for p in positive:
        if re.findall(p, text, re.I):
            sentiment += 1

    for n in negative:
        if re.findall(n, text, re.I):
            sentiment -= 1

    if sentiment > 0:
        return 'POSITIVE'
    elif sentiment < 0:
        return 'NEGATIVE'
    else:
        return 'COMMENT'


class LaunchPadReview(object):
    pass


class GithubReview(object):
    pass


def refresh_all():
    r = DBSession.query(Review).all()
    lp = get_lp()
    for review in r:
        refresh(review)


def refresh_bug(record):
    lp = get_lp()
    item = lp.load(record.api_url)

    record.state = bug_state(item)
    record.title = item.title



def refresh(record):
    if not record.api_url:
        return False

    if record.type == 'NEW':
        refresh_bug(record)
    elif record.type == 'UPDATE':
        refresh_merge(record)
    else:
        raise Exception('Turn down for what')
