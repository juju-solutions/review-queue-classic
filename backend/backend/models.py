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
    title = Column(Text)
    type = Column(Enum('NEW', 'UPDATE'))
    url = Column(Text)
    api_url = Column(Text)
    state = Column(Enum('PENDING', 'REVIEWED', 'MERGED', 'CLOSED', 'ABANDONDED',
                        'READY'))
    created = Column(DateTime, default=datetime.datetime.now)
    updated = Column(DateTime, default=datetime.datetime.now)
    category = relationship('ReviewCategory')
    source = relationship('Source')
    project = relationship('Project')
    votes = relationship('ReviewVotes')

    @pyramid.decorator.reify
    def age(self):
        d = datetime.datetime.now() - self.updated
        hours = d.seconds * 60 * 60
        if hours > 48:
            return '%s d' % d.days

        return '%s h' % hours


class ReviewVotes(Base):
    __tablename__ = 'review_votes'
    id = Column(Integer, primary_key=True)
    reviewer_id = Column(Integer, ForeignKey('reviewer.id'))
    review_id = Column(Integer, ForeignKey('review.id'))
    votes = Column(Enum('POSITIVE', 'NEGATIVE'))
    reviewer = relationship('Reviewer', backref=backref('votes'))


class ReviewCategory(Base):
    __tablename__ = 'review_category'
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    slug = Column(Text)


class Reviewer(Base):
    __tablename__ = 'reviewer'
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    is_charmer = Column(Boolean)
    profiles = relationship('Profile')


class Profile(Base):
    __tablename__ = 'profile'
    id = Column(Integer, primary_key=True)
    reviewer_id = Column(Integer, ForeignKey('reviewer.id'))
    source_id = Column(Integer, ForeignKey('source.id'))
    created = Column(DateTime, default=datetime.datetime.now)
    updated = Column(DateTime, onupdate=datetime.datetime.now)
    source = relationship('Source')


class Source(Base):
    __tablename__ = 'source'
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    slug = Column(Text)


class Project(Base):
    __tablename__ = 'project'
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('source.id'))
    source = relationship('Source')
    name = Column(Text)
    url = Column(Text)
