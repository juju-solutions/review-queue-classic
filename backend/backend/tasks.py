import time
import transaction
import datetime

from .models import (
    DBSession,
    Source,
    Review,
    Profile,
    User,
    ReviewVote,
    Series,
)

from .helpers import (
    get_lp,
    wait_a_second,
    create_project,
    bug_state,
    map_lp_state,
    create_user,
    create_series,
    determine_sentiment,
    create_vote,
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
    LaunchPad(get_lp(True)).ingest()

class LaunchPad(object):
    def __init__(self, lp):
        if not lp:
            lp = get_lp()

        self.lp = lp
        self.charmers = lp.people['charmers']

    def ingest(self):
        self.get_bugs()
        self.get_merges()

    def get_merges(self):
        #proposals = charmers.getRequestedReviews()
        b = self.charmers.getBranches()

        for branch in b:
            m = branch.getMergeProposals(status=['Work in progress',
                                                 'Needs review', 'Approved',
                                                 'Rejected', 'Merged',
                                                 'Code failed to merge', 'Queued',
                                                 'Superseded'])
            for merge in m:
                self.create_from_merge(merge)

    def get_bugs(self):
        charm = self.lp.distributions['charms']
        branch_filter = "Show only Bugs with linked Branches"
        tasks = charm.searchTasks(linked_branches=branch_filter,
                                  status=['New', 'Incomplete', 'Opinion',
                                          "Won't Fix", 'Confirmed', 'Triaged',
                                          'In Progress', 'Fix Committed',
                                          'Fix Released', 'Invalid',
                                          'Incomplete (with response)',
                                          'Incomplete (without response)'])
        for task in tasks:
            if '+source' in task.web_link:
                continue
            self.create_from_bug(task, task.bug)

    def skip_refresh(self, record):
        if not record or not record.syncd:
            return (False, None)

        rt = {'_default': 10,
              'REVIEWED': 60,
              'IN PROGRESS': 60,
              'MERGED': 720,
              'ABANDONDED': 900,
              'CLOSED': 720,
             }

        timedelta = datetime.datetime.utcnow() - record.syncd
        diff = divmod(timedelta.days * 86400 + timedelta.seconds, 60)
        timelimit = rt['_default'] if record.state not in rt else rt[record.state]
        return (diff[0] < timelimit, timelimit - diff[0])

    @wait_a_second
    def create_from_merge(self, task):
        active = True
        with transaction.manager:
            r = DBSession.query(Review).filter_by(api_url=task.self_link).first()
            skip_data = self.skip_refresh(r)
            if skip_data[0]:
                print("SKIP: %s (%s mins left)" % (task, skip_data[1]))
                return

            if not r:
                r = Review(type='UPDATE', api_url=task.self_link,
                           created=task.date_created.replace(tzinfo=None))

            print(task)
            title = task.source_branch.display_name
            r.url = task.web_link
            r.title = title=title
            prevstate = r.state
            r.state = map_lp_state(task.queue_status)
            r.owner = create_user(task.registrant)
            r.source = DBSession.query(Source).filter_by(slug='lp').one()
            r.syncd = datetime.datetime.utcnow()

            if task.target_branch.sourcepackage:
                series_data = task.target_branch.sourcepackage.distroseries
                r.series = create_series(series_data)
                active = r.series.active

            if r.series and not r.series.active:
                r.state = 'ABANDONDED'

            comments = task.all_comments

            prev = r.updated
            if len(comments) > 0:
                r.updated = comments[len(comments)-1].date_created.replace(tzinfo=None)
            else:
                r.updated = task.date_created.replace(tzinfo=None)

            if r.updated != prev or r.state != prevstate:
                r.unlock()

            if r.state in ['REVIEWED', 'CLOSED'] and len(comments) > 0:
                if comments[len(comments)-1].author == task.registrant:
                    r.state = 'FOLLOW UP'

            DBSession.add(r)

        if active:
            self.parse_comments(comments, r)
        else:
            print("Old ass shit, skipping")

    @wait_a_second
    def create_from_bug(self, task, bug):
        prev = None
        with transaction.manager:
            r = DBSession.query(Review).filter_by(api_url=task.self_link).first()

            skip_data = self.skip_refresh(r)
            if skip_data[0]:
                print("SKIP: %s (%s mins left)" % (task, skip_data[1]))
                return

            if not r:
                r = Review(type='NEW', api_url=task.self_link,
                           created=task.date_created.replace(tzinfo=None))
            else:
                prev = r

            print(task)
            r.title = bug.title
            r.url = task.web_link
            r.state = bug_state(task)
            r.updated = bug.date_last_message.replace(tzinfo=None) if bug.date_last_message > bug.date_last_updated else bug.date_last_updated.replace(tzinfo=None)

            if prev:
                if r.updated != prev.updated or r.state != prev.state:
                    r.unlock()

            r.owner = create_user(task.owner)
            r.source = DBSession.query(Source).filter_by(slug='lp').one()
            r.syncd = datetime.datetime.utcnow()

            if r.state in ['REVIEWED', 'CLOSED']:
                if bug.messages[len(bug.messages)-1].owner == task.assignee:
                    r.state = 'FOLLOW UP'

            DBSession.add(r)

        self.parse_messages(bug.messages, r)

    def parse_comments(self, comments, review):
        for m in comments:
            rv = (DBSession.query(ReviewVote)
                           .filter_by(comment_id=m.self_link)
                           .first()
                 )

            if rv and rv.created:
                print(m.self_link)
                continue

            vote = dict(vote=determine_sentiment(m.vote),
                        owner=create_user(m.author),
                        review=review,
                        comment_id=m.self_link,
                        created=m.date_created.replace(tzinfo=None),
                       )
            create_vote(vote)

    def parse_messages(self, comments, review):
        first = True
        for m in comments:
            if first:
                first = False # WTF
                continue
            rv = (DBSession.query(ReviewVote)
                           .filter_by(comment_id=m.self_link)
                           .first()
                 )

            if rv and rv.created:
                print(m.self_link)
                continue

            vote = dict(vote=determine_sentiment(m.content),
                        owner=create_user(m.owner),
                        review=review,
                        comment_id=m.self_link,
                        created=m.date_created.replace(tzinfo=None),
                       )

            create_vote(vote)

    def refresh(self, record):
        if not record.api_url:
            return False

        if record.type == 'NEW':
            self.create_from_bug(self.lp.load(record.api_url))
        elif record.type == 'UPDATE':
            self.create_from_merge(self.lp.load(record.api_url))
        else:
            raise Exception('Turn down for what')
