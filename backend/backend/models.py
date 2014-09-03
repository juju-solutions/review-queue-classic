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

    title = Column(Text)
    type = Column(Enum('NEW', 'UPDATE'))
    url = Column(Text)
    api_url = Column(Text)
    state = Column(Enum('PENDING', 'REVIEWED', 'MERGED', 'CLOSED', 'ABANDONDED',
                        'READY', 'NEW', 'IN PROGRESS', 'FOLLOW UP'))
    created = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    category = relationship('ReviewCategory')
    source = relationship('Source')
    project = relationship('Project')
    owner = relationship('User', backref=backref('reviews'))
    series = relationship('Series', backref=backref('reviews'))

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


class Profile(Base):
    __tablename__ = 'profile'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    source_id = Column(Integer, ForeignKey('source.id'))

    name = Column(Text)
    username = Column(Text)
    url = Column(Text)
    created = Column(DateTime(timezone=False), default=datetime.datetime.utcnow)
    updated = Column(DateTime(timezone=False), onupdate=datetime.datetime.utcnow)

    source = relationship('Source')
    user = relationship('User', backref=backref('profiles'))


class Address(Base):
    __tablename__ = 'emails'
    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('profile.id'))
    profile = relationship('Profile', backref=backref('addresses'))
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
