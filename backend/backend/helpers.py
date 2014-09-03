
import time

from launchpadlib.launchpad import Launchpad


def get_lp(login=False):
    # Make this a factory?
    if not login:
        return Launchpad.login_anonymously('review-queue', 'production', 'devel')


def wait_a_second(method):
    def wrapper(*args, **kw):
        start = int(round(time.time() * 1000))
        result = method(*args, **kw)
        end = int(round(time.time() * 1000))

        comptime = end - start
        if comptime < 1000:
            time.sleep((1000 - comptime) / 1000)

        return result
    return wrapper
