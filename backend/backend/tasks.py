import re
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


def get_all_the_things():
    lp = get_lp()
    charm = lp.distributions['charms']
    branch_filter = "Show only Bugs with linked Branches"
    bugs = charm.searchTasks(linked_branches=branch_filter)
    for bug in bugs:
        if '+source' in bug.web_link:
            continue
        create_if_not_already_a_review(bug,
                                       lp.bugs[int(''.join(bug.web_link.split('/')[-1:]))])

    #
    #proposals = charmers.getRequestedReviews()
    #b = charmers.getBranches()

    #for branch in b:
    #    m = branch.getMergeProposals()
    #    for merge in m:
    #        print merge.queue_status, merge.web_link


def map_lp_state(bug_task):
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
             }

    state = states[bug_task.status.lower()]
    if not bug_task.date_left_new and bug_task.status == 'New':
        return 'NEW'

    return states[bug_task.status.lower()]


def create_if_not_already_a_review(task, bug):
    try:
        DBSession.query(Review).filter_by(api_url=task.self_link).one()
    except:
        pass
    else:
        return
    print(bug)
    with transaction.manager:
        r = Review(title=bug.title, url=task.web_link, type='NEW',
                   state=map_lp_state(task), api_url=task.self_link,
                   created=task.date_created,
                   updated=bug.date_last_message if bug.date_last_message > bug.date_last_updated else bug.date_last_updated)
        r.owner = create_user(task.owner)
        r.source = DBSession.query(Source).filter_by(slug='lp').one()
        DBSession.add(r)

    load_comments(bug, DBSession.query(Review).filter_by(api_url=task.self_link).one())


def load_comments(bug, review):
    comments = bug.messages

    print('%s is the review id' % review.id)
    first = True
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

    positive = ['lgtm', '\+1']
    negative = ['nlgtm', '\-1 ', 'needs work']
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
