import datetime
import pyramid
import requests

from sqlalchemy import (
    Column,
    Integer,
    Text,
    Boolean,
    Enum,
    DateTime,
    ForeignKey,
    TypeDecorator,
)

from sqlalchemy.ext.declarative import declarative_base
from dateutil.tz import tzutc

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    backref,
)

from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))


class Base(object):
    @classmethod
    def get(cls, *args, **kw):
        if args:
            return DBSession.query(cls).get(*args)

        return (
            DBSession.query(cls)
            .filter_by(**kw)
            .first()
        )
Base = declarative_base(cls=Base)


class UTCDateTime(TypeDecorator):
    impl = DateTime

    def process_bind_param(self, value, engine):
        if value is not None:
            return value.replace(tzinfo=tzutc())

    def process_result_value(self, value, engine):
        if value is not None:
            return value.replace(tzinfo=None)


class Review(Base):
    __tablename__ = 'review'
    id = Column(Integer, primary_key=True)
    review_category_id = Column(Integer, ForeignKey('review_category.id'))
    source_id = Column(Integer, ForeignKey('source.id'))
    project_id = Column(Integer, ForeignKey('project.id'))
    user_id = Column(Integer, ForeignKey('user.id'))
    series_id = Column(Integer, ForeignKey('series.id'))
    lock_id = Column(Integer, ForeignKey('user.id'))

    title = Column(Text)
    type = Column(Enum('NEW', 'UPDATE', name='review_type'))
    url = Column(Text)
    api_url = Column(Text)
    test_url = Column(Text)
    state = Column(Enum(
        'PENDING', 'REVIEWED', 'MERGED', 'CLOSED', 'ABANDONDED',
        'READY', 'NEW', 'IN PROGRESS', 'FOLLOW UP', name='review_state'))

    created = Column(UTCDateTime, default=datetime.datetime.utcnow)
    updated = Column(UTCDateTime, default=datetime.datetime.utcnow)
    syncd = Column(UTCDateTime, default=datetime.datetime.utcnow,
                   onupdate=datetime.datetime.utcnow)
    locked = Column(UTCDateTime)

    category = relationship('ReviewCategory')
    source = relationship('Source')
    project = relationship('Project')
    series = relationship('Series', backref=backref('reviews'))
    owner = relationship('User', foreign_keys=[user_id],
                         backref=backref('reviews'))
    locker = relationship('User', foreign_keys=[lock_id],
                          backref=backref('locks'))

    def get_test_url(self):
        if self.test_url:
            return self.test_url

        if self.type == 'UPDATE':
            self.test_url = self.url
        elif self.type == 'NEW':
            from helpers import get_lp
            bug = get_lp().load(self.api_url).bug
            self.test_url = bug.linked_branches[0].branch.bzr_identity

        return self.test_url

    def get_tests_without_substrate(self):
        return (
            DBSession.query(ReviewTest)
            .filter_by(review_id=self.id)
            .filter_by(substrate=None)
        )

    def get_tests_for_retry(self):
        return (
            DBSession.query(ReviewTest)
            .filter_by(review_id=self.id)
            .filter_by(status='RETRY')
        )

    def get_tests_for_cancel(self):
        return (
            DBSession.query(ReviewTest)
            .filter_by(review_id=self.id)
            .filter(ReviewTest.status.in_([
                'RETRY',
                'PENDING',
                'RUNNING']))
        )

    def get_tests_overdue(self, timeout):
        tests = (
            DBSession.query(ReviewTest)
            .filter_by(review_id=self.id)
            .filter(ReviewTest.status.in_([
                'PENDING',
                'RUNNING']))
        )

        now = datetime.datetime.utcnow()
        return [
            t for t in tests
            if (now - t.updated).total_seconds() > timeout
        ]

    def create_tests(self, settings, substrates=None):
        if not self.id:
            DBSession.flush()
            assert self.id, 'Need Review.id to create tests'

        substrates = (
            substrates or
            settings['testing.default_substrates'].split(',')
        )
        review_tests = []
        # so we can correlate by `created` time later
        batch_time = datetime.datetime.utcnow()
        for substrate in substrates:
            review_tests.append(ReviewTest(
                status='RETRY',
                substrate=substrate.strip(),
                created=batch_time,
            ))
        self.tests.extend(review_tests)
        DBSession.flush()  # get ReviewTest ids

        for review_test in review_tests:
            review_test.send_ci_request(settings)

    def refresh_tests(self, settings):
        if self.state in ('ABANDONDED', 'CLOSED'):
            return self.cancel_tests()

        for t in self.get_tests_without_substrate():
            t.cancel()

        for t in self.get_tests_for_retry():
            t.send_ci_request(settings)

        timeout = int(settings.get(
            'testing.timeout', 60 * 60 * 24))
        for t in self.get_tests_overdue(timeout):
            if t.status == 'RUNNING':
                if t.try_finish():
                    continue
            t.send_ci_request(settings)

    def cancel_tests(self):
        for t in self.get_tests_for_cancel():
            t.cancel()

    @pyramid.decorator.reify
    def test_status(self):
        if not self.tests:
            return None

        def has_status(s):
            return [
                t for t in self.tests
                if t.status == s
            ]

        if any(has_status('PASS')):
            return 'PASS'

        if any(has_status('FAIL')):
            return 'FAIL'

        return 'QUEUED'

    @pyramid.decorator.reify
    def positive_votes(self):
        return [vote for vote in self.votes if vote.vote == 'POSITIVE']

    @pyramid.decorator.reify
    def negative_votes(self):
        return [vote for vote in self.votes if vote.vote == 'NEGATIVE']

    @pyramid.decorator.reify
    def age(self, use_updated=True):
        if use_updated:
            t = self.updated.replace(tzinfo=None)
        else:
            t = self.created.replace(tzinfo=None)

        d = datetime.datetime.utcnow() - t
        hours = d.seconds * 60 * 60
        if hours > 48:
            return '%s d' % d.days

        return '%s h' % hours

    def lock(self, user):
        self.locked = datetime.datetime.utcnow()
        self.locker = user

    def unlock(self):
        self.locked = None
        self.locker = None

    @pyramid.decorator.reify
    def user_followup(self):
        return self.state in ['REVIEWED', 'IN PROGRESS']

    @pyramid.decorator.reify
    def reviewer_followup(self):
        return self.state in ['READY', 'NEW', 'PENDING', 'FOLLOW UP']

    @pyramid.decorator.reify
    def state_inflect(self):
        return 'an' if self.state[0] in ['A', 'E', 'I', 'O', 'U'] else 'a'


class ReviewHistory(Base):
    __tablename__ = 'review_history'
    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey('review.id'))
    user_id = Column(Integer, ForeignKey('user.id'))

    what = Column(Text)
    prev = Column(Text)
    new = Column(Text)

    user = relationship('User', backref=backref('actions'))
    review = relationship('Review', backref=backref('history'))


class ReviewTest(Base):
    __tablename__ = 'review_test'
    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey('review.id'))
    requester_id = Column(Integer, ForeignKey('user.id'))
    status = Column(Text)  # RETRY, PENDING, PASS, FAIL
    substrate = Column(Text)
    url = Column(Text)

    created = Column(UTCDateTime, default=datetime.datetime.utcnow)
    updated = Column(UTCDateTime, default=datetime.datetime.utcnow,
                     onupdate=datetime.datetime.utcnow)
    finished = Column(UTCDateTime)

    review = relationship(
        'Review',
        backref=backref('tests'),
        order_by="ReviewTest.id"
    )
    requester = relationship('User')

    def send_ci_request(self, settings):
        req_url = settings['testing.jenkins_url']
        callback_url = (
            '{}/review/{}/ctb_callback/{}'.format(
                settings['app.url'],
                self.review.id,
                self.id,
            )
        )

        req_params = {
            'url': self.review.get_test_url(),
            'token': settings['testing.jenkins_token'],
            'cause': 'Review Queue Ingestion',
            'callback_url': callback_url,
            'job_id': self.id,
            'envs': self.substrate,
        }

        r = requests.get(req_url, params=req_params)

        if r.status_code == requests.codes.ok:
            self.status = 'PENDING'
            self.updated = datetime.datetime.utcnow()

    def try_finish(self):
        """Attempt to find a CI result for this ReviewTest
        and update the ReviewTest accordingly.

        Returns True if successful, else False.

        """
        if self.status != 'RUNNING' or not self.url:
            return False

        result_url = '{}artifact/results.json'.format(self.url)
        try:
            result_data = requests.get(result_url).json()
        except:
            return False

        from .tasks import update_lp_item

        passed = all(
            test.get('returncode', 0) == 0
            for test in result_data.get('tests', {})
        )
        self.status = 'PASS' if passed else 'FAIL'
        self.finished = datetime.datetime.strptime(
            result_data['finished'],
            '%Y-%m-%dT%H:%M:%SZ'
        )
        update_lp_item.delay(self)

        return True

    def cancel(self):
        self.status = 'CANCELED'
        self.finished = datetime.datetime.utcnow()


class ReviewVote(Base):
    __tablename__ = 'review_vote'
    id = Column(Integer, primary_key=True)
    comment_id = Column(Text)
    user_id = Column(Integer, ForeignKey('user.id'))
    review_id = Column(Integer, ForeignKey('review.id'))

    vote = Column(Enum(
        'POSITIVE', 'NEGATIVE', 'COMMENT', name='reviewvote_vote'))
    created = Column(UTCDateTime)

    owner = relationship('User', backref=backref('votes'))
    review = relationship('Review', backref=backref('votes'))

    @pyramid.decorator.reify
    def updated(self):
        return self.review.updated.replace(tzinfo=None)


class ReviewCategory(Base):
    __tablename__ = 'review_category'
    id = Column(Integer, primary_key=True)

    name = Column(Text)
    slug = Column(Text)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)

    name = Column(Text)
    is_charmer = Column(Boolean, default=False)
    is_community = Column(Boolean, default=False)
    is_contributor = Column(Boolean, default=False)


class Profile(Base):
    __tablename__ = 'profile'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    source_id = Column(Integer, ForeignKey('source.id'))

    name = Column(Text)
    username = Column(Text)
    url = Column(Text)
    claimed = Column(Text)

    created = Column(UTCDateTime, default=datetime.datetime.utcnow)
    updated = Column(UTCDateTime, onupdate=datetime.datetime.utcnow)

    source = relationship('Source')
    user = relationship('User', backref=backref('profiles'))


class Address(Base):
    __tablename__ = 'emails'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    profile_id = Column(Integer, ForeignKey('profile.id'))
    user = relationship('User', backref=backref('addresses'))
    email = Column(Text)


class Source(Base):
    __tablename__ = 'source'
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    slug = Column(Text)


class Series(Base):
    __tablename__ = 'series'
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    slug = Column(Text)
    active = Column(Boolean, default=True)


class Project(Base):
    __tablename__ = 'project'
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    url = Column(Text)
