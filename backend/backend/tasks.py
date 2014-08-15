import re
import pytz
import transaction

from .models import (
    DBSession,
    Source,
    Review,
    Profile,
    User,
    ReviewVote,
)

from .helpers import get_lp
from sqlalchemy import engine_from_config

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
    proposals = charmers.getRequestedReviews()
    b = charmers.getBranches()

    for branch in b:
        m = branch.getMergeProposals()
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
    # 'NEW', 'PENDING', 'REVIEWED', 'MERGED', 'CLOSED', 'READY', 'ABANDONDED', IN PROGRESS
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
              'rejected': 'CLOSED',
              'merged': 'CLOSED',
             }

    return states[state.lower()]


def create_review_from_merge(task):
    try:
        DBSession.query(Review).filter_by(api_url=task.self_link).one()
    except:
        pass
    else:
        return
    print(task)
    with transaction.manager:
        title = "Merge %s into %s" % (task.source_branch.display_name,
                                      task.target_branch.display_name)
        r = Review(title=title, url=task.web_link, type='UPDATE',
                   state=map_lp_state(task.queue_status),
                   api_url=task.self_link,
                   created=task.date_created.replace(tzinfo=None))
        r.owner = create_user(task.registrant)
        r.source = DBSession.query(Source).filter_by(slug='lp').one()
        comments = task.all_comments

        if len(comments) > 0:
            r.updated = comments[len(comments)-1].date_created.replace(tzinfo=None)
        else:
            r.updated = task.date_created.replace(tzinfo=None)

        DBSession.add(r)

    review = DBSession.query(Review).filter_by(api_url=task.self_link).one()
    parse_comments(task.all_comments, review)


def create_review_from_bug(task, bug):
    try:
        DBSession.query(Review).filter_by(api_url=task.self_link).one()
    except:
        pass
    else:
        return
    print(bug)
    with transaction.manager:
        r = Review(title=bug.title, url=task.web_link, type='NEW',
                   state=bug_state(task), api_url=task.self_link,
                   created=task.date_created,
                   updated=bug.date_last_message if bug.date_last_message > bug.date_last_updated else bug.date_last_updated)
        r.owner = create_user(task.owner)
        r.source = DBSession.query(Source).filter_by(slug='lp').one()
        DBSession.add(r)

    parse_messages(bug.messages,
                  DBSession.query(Review).filter_by(api_url=task.self_link).one())


def parse_comments(comments, review):
    for m in comments:
        try:
            DBSession.query(ReviewVote).filter_by(comment_id=m.self_link).one()
        except:
            pass
        else:
            print(m.self_link)
            continue

        with transaction.manager:
            s = determine_sentiment(m.vote)
            u = create_user(m.author)
            v = ReviewVote(vote=s, comment_id=m.self_link)
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
        except:
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
    try:
        p = DBSession.query(Profile).filter_by(url=profile.web_link).one()
    except:
        pass
    else:
        return p.user

    with transaction.manager:
        # It's an LP profile
        p = Profile(name=profile.display_name, username=profile.name,
                    url=profile.web_link)
        p.source = DBSession.query(Source).filter_by(slug='lp').one()

        r = User(name=profile.display_name,
                 is_charmer=profile in charmers.members)
        p.user = r
        DBSession.add(r)
        DBSession.add(p)

    return DBSession.query(Profile).filter_by(url=profile.web_link).one().user


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


def refresh_record(record):
    if not record.api_url:
        return False

    lp = get_lp()
    item = lp.load(record.api_url)
    record.state = map_lp_state(item.status)
