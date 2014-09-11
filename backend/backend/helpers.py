import re
import time
import datetime
import transaction

from launchpadlib.launchpad import Launchpad
from marshmallow import Serializer, fields

from pyramid.events import subscriber

from pyramid.events import (
    BeforeRender,
    NewRequest,
)

from .models import (
    DBSession,
    User,
    Project,
    Source,
    Profile,
    ReviewVote,
    Series,
)

def create_project(name):
    p = DBSession.query(Project).filter_by(name=name.lower()).first()

    if p:
        return p

    with transaction.manager:
        p = Project(name=name.lower())
        DBSession.add(p)

    return p


def bug_state(bug_task):
    if not bug_task.date_left_new and bug_task.status == 'New':
        return 'NEW'

    return map_lp_state(bug_task.status)


def map_lp_state(state):
    # 'NEW', 'PENDING', 'REVIEWED', 'MERGED', 'CLOSED', 'READY', 'ABANDONDED',
    # 'IN PROGRESS', 'FOLLOW UP'
    states = {'new': 'PENDING',
              'incomplete': 'REVIEWED',
              'incomplete (without response)': 'REVIEWED',
              'incomplete (with response)': 'FOLLOW UP',
              'opinion': 'CLOSED',
              'invalid': 'CLOSED',
              "won't fix": 'ABANDONDED',
              "expired": 'ABANDONDED',
              'confirmed': 'PENDING',
              'triaged': 'PENDING',
              'in progress': 'IN PROGRESS',
              'fix committed': 'READY',
              'fix released': 'CLOSED',
              'needs review': 'PENDING',
              'work in progress': 'IN PROGRESS',
              'approved': 'READY',
              'rejected': 'ABANDONDED',
              'merged': 'MERGED',
              'superseded': 'ABANDONDED',
              'queued': 'PENDING',
              'code failed to merge': 'FOLLOW UP',
             }

    return states[state.lower()]


def create_vote(vote):
    with transaction.manager:
        rv = (DBSession.query(ReviewVote)
                       .filter_by(comment_id=vote['comment_id'])
                       .first()
             )

        if not rv:
            rv = ReviewVote()
            print("Creating %s" % vote['comment_id'])
        else:
            print("Updating %s" % vote['comment_id'])

        rv.vote = vote['vote']
        rv.owner = vote['owner']
        rv.comment_id = vote['comment_id']
        rv.review = vote['review']
        rv.created = vote['created']

        return rv


def create_user(profile):
    p = DBSession.query(Profile).filter_by(url=profile.web_link).first()

    if p:
        return p.user

    with transaction.manager:
        # It's an LP profile
        p = Profile(name=profile.display_name, username=profile.name,
                    url=profile.web_link)
        p.source = DBSession.query(Source).filter_by(slug='lp').first()

        r = User(name=profile.display_name,
                 is_charmer=profile in get_lp().people['charmers'].members)
        p.user = r
        DBSession.add(r)
        DBSession.add(p)

    return DBSession.query(Profile).filter_by(url=profile.web_link).first().user


def create_series(series):
    series_slug = series.name.replace(' ', '_')
    s = DBSession.query(Series).filter_by(slug=series_slug).first()

    if s:
        return s

    with transaction.manager:
        s = Series(slug=series_slug, name=series.name, active=series.active)
        DBSession.add(s)

    return DBSession.query(Series).filter_by(slug=series_slug).one()


def determine_sentiment(text):
    if not text:
        return 'COMMENT'

    positive = ['lgtm', '\+1', 'approve']
    negative = ['nlgtm', '\-1 ', 'needs work', 'needs fixing',
                'needs information', 'disapprove', 'resubmit', 'dnlgtm']
    sentiment = 0
    for p in positive:
        if re.findall(p, text, re.I):
            sentiment += 1

    for n in negative:
        if re.findall(n, text, re.I):
            sentiment -= 1

    if sentiment > 0:
        return 'POSITIVE'
    elif sentiment < 0:
        return 'NEGATIVE'
    else:
        return 'COMMENT'


@subscriber(NewRequest)
def setup_user(event):
    if 'user' in event.request.session:
        event.request.session['User'] = DBSession.query(User).get(event.request.session['user'])


@subscriber(BeforeRender)
def add_global(event):
    import pkg_resources
    event['version'] = pkg_resources.get_distribution("backend").version


def get_lp(login=False):
    def no_creds():
        pass

    if not login:
        return Launchpad.login_anonymously('review-queue', 'production')

    return Launchpad.login_with('review-queue', 'production',
                                credentials_file='lp-creds',
                                credential_save_failed=no_creds)


def login(login=False):
    lp = get_lp(True)
    return lp.me




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


class SourceSerializer(Serializer):
    class Meta:
        fields = ('slug', 'name')


class ProfileSerializer(Serializer):
    source = fields.Nested(SourceSerializer)

    class Meta:
        fields = ('name', 'username', 'url', 'source')


class UserSerializer(Serializer):
    reviews = fields.Method('reviews_map')
    profiles = fields.Method('profiles_map')
    charmer = fields.Method('charmer_map')

    def reviews_map(self, u):
        return ReviewSerializer(u.reviews, many=True, exclude=('owner')).data

    def charmer_map(self, f):
        return f.is_charmer

    def profiles_map(self, f):
        return ProfileSerializer(f.profiles, many=True).data

    class Meta:
        fields = ('id', 'name', 'charmer', 'profiles', 'reviews')


class ReviewSerializer(Serializer):
    owner = fields.Method('owner_map')

    def owner_map(self, r):
        return UserSerializer(r.owner, exclude=('reviews', 'profiles', )).data

    class Meta:
        fields = ('id', 'title', 'type', 'url', 'state', 'owner', 'created', 'updated')


class ReviewedSerializer(Serializer):
    id = fields.Method('id_map')
    title = fields.Method('title_map')
    type = fields.Method('rtype_map')
    url = fields.Method('url_map')
    owner = fields.Method('owner_map')
    state = fields.Method('state_map')
    created = fields.Method('created_map')
    updated = fields.Method('updated_map')

    def id_map(self, r):
        return r.review.id

    def title_map(self, r):
        return r.review.title

    def type_map(self, r):
        return r.review.type

    def url_map(self, r):
        return r.review.url

    def owner_map(self, r):
        return UserSerializer(r.review.owner, exclude=('reviews', 'profiles', )).data

    def state_map(self, r):
        return r.review.state

    def created_map(self, r):
        return r.review.created.strftime('%Y-%m-%dT%H:%M:%S')

    def updated_map(self, r):
        return r.review.updated.strftime('%Y-%m-%dT%H:%M:%S')

    class Meta:
        fields = ('id', 'title', 'type', 'url', 'owner', 'state', 'created', 'updated')
