
import transaction

from launchpadlib.launchpad import Launchpad

from .models import (
    DBSession,
    Source,
    Review,
)

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
)


settings = get_appsettings('development.ini', options={})
engine = engine_from_config(settings, 'sqlalchemy.')
DBSession.configure(bind=engine)


def get_lp(login=False):
    # Make this a factory?
    if not login:
        return Launchpad.login_anonymously('review-queue', 'production', 'devel')


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

    #charmers = lp.people['charmers']
    #proposals = charmers.getRequestedReviews()
    #b = charmers.getBranches()

    #for branch in b:
    #    m = branch.getMergeProposals()
    #    for merge in m:
    #        print merge.queue_status, merge.web_link


def map_lp_state(status):
    # 'PENDING', 'REVIEWED', 'MERGED', 'CLOSED', 'READY'
    states = {'new': 'PENDING', 'incomplete': 'REVIEWED', 'opinion': 'CLOSED', 'invalid': 'CLOSED', "won't fix": 'ABANDONDED', 'confirmed': 'PENDING', 'triaged': 'PENDING', 'in progress': 'PENDING', 'fix committed': 'READY', 'fix released': 'CLOSED'}
    return states[status.lower()]

def create_if_not_already_a_review(task, bug):
    try:
        DBSession.query(Review).filter_by(api_url=task.self_link).one()
    except:
        print("roll out")
        pass
    else:
        return

    with transaction.manager:
        r = Review(title=bug.title, url=task.web_link, type='NEW',
                   state=map_lp_state(task.status), api_url=task.self_link,
                   created=task.date_created,
                   updated=bug.date_last_message if bug.date_last_message > bug.date_last_updated else bug.date_last_updated)
        r.source = DBSession.query(Source).filter_by(slug='lp').one()
        DBSession.add(r)


def fetch_review():
    pass


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
