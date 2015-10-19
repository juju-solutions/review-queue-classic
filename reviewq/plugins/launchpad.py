import transaction
import datetime

from ..models import (
    DBSession,
    Source,
    Review,
    ReviewVote,
)

from ..helpers import (
    wait_a_second,
    bug_state,
    map_lp_state,
    create_user,
    create_series,
    determine_sentiment,
    create_vote,
    get_lp
)

from lazr.restfulclient import errors

from ..plugin import SourcePlugin


class LaunchPad(SourcePlugin):
    def __init__(self, settings, log=None):
        try:
            self.lp = get_lp(True)
        except:
            self.lp = get_lp()

        self.settings = settings
        super(LaunchPad, self).__init__(log)

    def ingest(self, person):
        self.person = self.lp.people[person]
        self.get_bugs()
        self.get_merges()

    def get_merges(self):
        b = self.person.getBranches()

        for branch in b:
            m = branch.getMergeProposals(status=['Work in progress',
                                                 'Needs review', 'Approved',
                                                 'Rejected', 'Merged',
                                                 'Code failed to merge',
                                                 'Queued',
                                                 'Superseded'])
            for merge in m:
                r = Review.get(api_url=merge.self_link)
                if not r:
                    self.create_from_merge(merge)

    def get_bugs(self):
        charm = self.lp.distributions['charms']
        branch_filter = "Show only Bugs with linked Branches"
        #branch_filter = 'Show all bugs'
        tasks = charm.searchTasks(linked_branches=branch_filter,
                                  tags=['-not-a-charm'],
                                  status=['New', 'Incomplete', 'Opinion',
                                          "Won't Fix", 'Confirmed', 'Triaged',
                                          'In Progress', 'Fix Committed',
                                          'Fix Released', 'Invalid',
                                          'Incomplete (with response)',
                                          'Incomplete (without response)'])
        for task in tasks:
            if '+source' in task.web_link:
                continue
            r = Review.get(api_url=task.self_link)
            if not r:
                self.create_from_bug(task)

    def skip_refresh(self, record):
        if not record or not record.syncd:
            return (False, None)

        rt = {
            '_default': 10,
            'REVIEWED': 60,
            'IN PROGRESS': 60,
            'MERGED': 720,
            'ABANDONDED': 900,
            'CLOSED': 720,
        }

        timedelta = datetime.datetime.utcnow() - record.syncd
        diff = divmod(timedelta.days * 86400 + timedelta.seconds, 60)
        timelimit = (rt['_default'] if record.state not in rt
                     else rt[record.state])
        return (diff[0] < timelimit, timelimit - diff[0])

    @wait_a_second
    def create_from_merge(self, task):
        active = True
        with transaction.manager:
            r = Review.get(api_url=task.self_link)
            if not r:
                r = Review(
                    type='UPDATE',
                    api_url=task.self_link,
                    created=task.date_created.replace(tzinfo=None)
                )
                r.source = Source.get(slug='lp')
                DBSession.add(r)
                if (map_lp_state(task.queue_status) not in
                        ('ABANDONED', 'CLOSED', 'MERGED')):
                    r.create_tests(self.settings)
            else:
                r.refresh_tests(self.settings)

            prev_state = r.state
            prev_updated = r.updated

            r.title = task.source_branch.display_name
            r.url = task.web_link
            r.test_url = r.url
            r.state = map_lp_state(task.queue_status)
            r.owner = create_user(task.registrant)
            r.syncd = datetime.datetime.utcnow()

            if task.target_branch.sourcepackage:
                series_data = task.target_branch.sourcepackage.distroseries
                r.series = create_series(series_data)
                active = r.series.active

            if r.series and not r.series.active:
                r.state = 'ABANDONDED'

            comments = task.all_comments

            if len(comments) > 0:
                last_comment = comments[len(comments) - 1]
                r.updated = last_comment.date_created.replace(tzinfo=None)
                if (r.state in ('REVIEWED', 'CLOSED') and
                        last_comment.author == task.registrant):
                    r.state = 'FOLLOW UP'
            else:
                r.updated = task.date_created.replace(tzinfo=None)

            if r.updated != prev_updated or r.state != prev_state:
                r.unlock()

        if active:
            self.parse_comments(comments, r)

    @wait_a_second
    def create_from_bug(self, task):
        bug = task.bug
        with transaction.manager:
            r = Review.get(api_url=task.self_link)
            if not r:
                r = Review(
                    type='NEW',
                    api_url=task.self_link,
                    created=task.date_created.replace(tzinfo=None)
                )
                r.source = Source.get(slug='lp')
                DBSession.add(r)
                if (bug_state(task.queue_status) not in
                        ('ABANDONED', 'CLOSED', 'MERGED')):
                    r.create_tests(self.settings)
            else:
                r.refresh_tests(self.settings)

            r.title = bug.title
            r.owner = create_user(task.owner)
            r.url = task.web_link
            r.test_url = bug.linked_branches[0].branch.bzr_identity
            r.syncd = datetime.datetime.utcnow()
            state = bug_state(task)
            updated = (
                bug.date_last_message.replace(tzinfo=None)
                if bug.date_last_message > bug.date_last_updated
                else bug.date_last_updated.replace(tzinfo=None)
            )

            if updated != r.updated or state != r.state:
                r.state = state
                r.updated = updated
                r.unlock()

            if r.state in ('REVIEWED', 'CLOSED'):
                if bug.messages[len(bug.messages) - 1].owner == task.assignee:
                    r.state = 'FOLLOW UP'

            if 'not-a-charm' in bug.tags:
                r.state = 'ABANDONDED'

        self.parse_messages(bug.messages, r)

    def parse_comments(self, comments, review):
        for m in comments:
            rv = ReviewVote.get(comment_id=m.self_link)

            if rv and rv.created:
                continue

            vote = dict(
                vote=determine_sentiment(m.vote),
                owner=create_user(m.author),
                review=review,
                comment_id=m.self_link,
                created=m.date_created.replace(tzinfo=None),
            )

            with transaction.manager:
                create_vote(vote)

    def parse_messages(self, comments, review):
        for m in comments[1:len(comments)]:
            rv = ReviewVote.get(comment_id=m.self_link)

            if rv and rv.created:
                continue

            vote = dict(
                vote=determine_sentiment(m.content),
                owner=create_user(m.owner),
                review=review,
                comment_id=m.self_link,
                created=m.date_created.replace(tzinfo=None),
            )

            with transaction.manager:
                create_vote(vote)

    def refresh(self, record=None, id=None):
        if not record and not id:
            raise Exception('Need something to refresh')

        if not record:
            record = Review.get(id)

        if not record.api_url:
            return False

        try:
            task = self.lp.load(record.api_url)
        except errors.NotFound:
            # It was deleted, or something
            DBSession.add(record)
            record.status = 'ABANDONDED'
            record.cancel_tests()
            transaction.commit()
            return
        except ValueError:
            DBSession.add(record)
            record.status = 'CLOSED'
            record.cancel_tests()
            transaction.commit()
            return

        if record.type == 'NEW':
            self.create_from_bug(task)
        elif record.type == 'UPDATE':
            self.create_from_merge(task)
        else:
            raise Exception('Turn down for what')
