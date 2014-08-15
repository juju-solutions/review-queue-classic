
from launchpadlib.launchpad import Launchpad


def get_lp(login=False):
    # Make this a factory?
    if not login:
        return Launchpad.login_anonymously('review-queue', 'production', 'devel')
