from sqlalchemy import (
    Column,
    Index,
    Integer,
    Text,
    Boolean,
    Enum,
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
    review_type_id = Column(Integer, ForeignKey('review_type.id'))
    review_category_id = Column(Integer, ForeignKey('review_category.id'))
    source_id = Column(Integer, ForeignKey('source.id'))
    project_id = Column(Integer, ForeignKey('project.id'))
    title = Column(Text)
    url = Column(Text)
    state = Enum('PENDING', 'REVIEWED', 'MERGED', 'CLOSED', 'READY')
    relationship('ReviewType', backref=backref("review_type", uselist=False))
    relationship('ReviewCategory', backref=backref("review_category",
                                                   uselist=False))
    relationship('Source', backref=backref("source", uselist=False))
    relationship('Project', backref=backref("project", uselist=False))


class ReviewType(Base):
    __tablename__ = 'review_type'
    id = Column(Integer, primary_key=True)
    name = Column(Text)


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
