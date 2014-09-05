
import time

from launchpadlib.launchpad import Launchpad
from marshmallow import Serializer, fields


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
