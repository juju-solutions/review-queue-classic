import datetime
import pyramid

from sqlalchemy import (
    Column,
    Index,
    Integer,
    Text,
    Boolean,
    Enum,
    DateTime,
    ForeignKey,
)

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    backref,
)

from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


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
    type = Column(Enum('NEW', 'UPDATE'))
    url = Column(Text)
    api_url = Column(Text)
    state = Column(Enum('PENDING', 'REVIEWED', 'MERGED', 'CLOSED', 'ABANDONDED',
                        'READY', 'NEW', 'IN PROGRESS', 'FOLLOW UP'))

    created = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    syncd = Column(DateTime(timezone=True),
                   default=datetime.datetime.utcnow,
                   onupdate=datetime.datetime.utcnow)
    locked = Column(DateTime(timezone=True))

    category = relationship('ReviewCategory')
    source = relationship('Source')
    project = relationship('Project')
    series = relationship('Series', backref=backref('reviews'))
    owner = relationship('User', foreign_keys=[user_id],
                         backref=backref('reviews'))
    locker = relationship('User', foreign_keys=[lock_id],
                          backref=backref('locks'))

    @pyramid.decorator.reify
    def positive_votes(self):
        return [vote for vote in self.votes if vote.vote == 'POSITIVE']

    @pyramid.decorator.reify
    def negative_votes(self):
        return [vote for vote in self.votes if vote.vote == 'NEGATIVE']

    @pyramid.decorator.reify
    def age(self):
        d = datetime.datetime.utcnow() - self.updated
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


class ReviewTest(Base):
    __tablename__ = 'review_test'
    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey('review.id'))
    status = Column(Text)  # PENDING, PASS, FAIL?
    url = Column(Text)

    created = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    finished = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    review = relationship('Review', backref=backref('tests'))


class ReviewVote(Base):
    __tablename__ = 'review_vote'
    id = Column(Integer, primary_key=True)
    comment_id = Column(Text)
    user_id = Column(Integer, ForeignKey('user.id'))
    review_id = Column(Integer, ForeignKey('review.id'))

    vote = Column(Enum('POSITIVE', 'NEGATIVE', 'COMMENT'))
    created = Column(DateTime(timezone=True))

    owner = relationship('User', backref=backref('votes'))
    review = relationship('Review', backref=backref('votes'))

    @pyramid.decorator.reify
    def updated(self):
        return self.review.updated


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

    created = Column(DateTime(timezone=False), default=datetime.datetime.utcnow)
    updated = Column(DateTime(timezone=False), onupdate=datetime.datetime.utcnow)

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
