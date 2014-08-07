
from launchpadlib.launchpad import Launchpad

from .models import (
    DBSession,
    Review,
)


def get_all_the_things():
    lp = Launchpad.login_anonymously('review-queue', 'production', 'devel')
    charm = lp.distributions['charms']
    branch_filter = "Show only Bugs with linked Branches"
    bugs = charm.searchTasks(linked_branches=branch_filter)
    for bug in bugs:
        if '+source' not in bug.web_link:
             print bug

    charmers = lp.people['charmers']
    proposals = charmers.getRequestedReviews()
    b = charmers.getBranches()

    for branch in b:
        m = branch.getMergeProposals()
        for merge in m:
            print merge.queue_status, merge.web_link

def refresh_record(record):
    pass
