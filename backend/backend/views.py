import re
import sqlalchemy

from datetime import date

from pyramid.httpexceptions import (
    HTTPFound,
    HTTPNotFound,
    )

from pyramid.view import view_config

from .models import (
    DBSession,
    Review,
    Profile,
    User,
    ReviewVote,
    )

from .helpers import (
    UserSerializer,
    ReviewSerializer,
    ReviewedSerializer,
)


@view_config(route_name='home', renderer='templates/dashboard.pt')
def dashboard(request):
    #reviews = DBSession.query(Review).group_by(Review.review_category_id).all()
    reviews = DBSession.query(Review).filter(Review.state != 'REVIEWED',
                                             Review.state != 'NEW',
                                             Review.state != 'IN PROGRESS',
                                             Review.state != 'CLOSED',
                                             Review.state != 'MERGED',
                                             Review.state != 'ABANDONDED').order_by(Review.updated).all()
    incoming = DBSession.query(Review).filter_by(state='NEW').order_by(Review.updated).all()
    return dict(reviews=reviews, incoming=incoming)


@view_config(route_name='find_user', renderer='templates/user.pt')
def find_user(req):
    username = req.params.get('user')
    lpuser = req.cookies.get('lpuser')

    if not lpuser and username:
        profile = DBSession.query(Profile).filter_by(username=username).first()
        if not profile:
            return dict(error='No profile found')
        lpuser = username

    if not lpuser:
        return dict(user=dict(), reviews=dict(), submitted=dict(), me=True)

    req.matchdict['username'] = lpuser
    return user(req)


@view_config(route_name='search_user', renderer='json')
def search_user(req):
    query = req.params['q']
    matches = DBSession.query(User).filter(User.name.like('%%%s%%' % query)).all()
    return UserSerializer(matches, many=True, exclude=('reviews', )).data


@view_config(route_name='query_results', renderer='templates/search.pt')
def saved_search(request):
    q = request.matchdict['filter']

    #return search(request, q)



@view_config(route_name='query', renderer='templates/search.pt')
def serach(request):
    filters = {'reviewer': None,
               'owner': None,
               'from': None,
               'to': None,
               'source': None,
               'state': None,
              }
    if not request.params:
        return dict(results=None)

    for f in filters:
        if f in request.params:
            val = request.params[f]
            if ',' in val:
                val = val.split(',')
            filters[f] = val

    q = DBSession.query(Review)

    if filters['owner']:
        if not isinstance(filters['owner'], list):
            filters['owner'] = [filters['owner']]
        q = q.filter(Review.user_id.in_(filters['owner']))
    if filters['state']:
        if not isinstance(filters['state'], list):
            filters['state'] = [filters['state']]
        q = q.filter(Review.state.in_(filters['state']))
    if filters['reviewer']:
        if not isinstance(filters['reviewer'], list):
            filters['reviewer'] = [filters['reviewer']]
        q = (q.join(ReviewVote.review)
              .filter(ReviewVote.user_id.in_(filters['reviewer'])))

    data = q.all()
    return dict(results=data)


@view_config(route_name='show_review', renderer='templates/show_review.pt')
@view_config(route_name='show_reviews', renderer='json')
def review(req):
    review_id = req.matchdict['review']
    review = DBSession.query(Review).filter_by(id=review_id).first()

    if not review:
        return HTTPNotFound('No such review')

    return dict((col.name, str(getattr(review, col.name))) for col in sqlalchemy.orm.class_mapper(review.__class__).mapped_table.c)


@view_config(route_name='view_user', accept="application/json", renderer='json')
def user_json(request):
    data = user(request)

    return dict(user=UserSerializer(data['user'], exclude=('reviews', )).data,
                reviews=ReviewedSerializer(data['reviews'], many=True).data,
                submitted=ReviewSerializer(data['submitted'], exclude=('owner', ), many=True).data)

@view_config(route_name='view_user', accept="text/html", renderer='templates/user.pt')
def user(request):
    username = request.matchdict['username']
    user = DBSession.query(Profile).filter_by(username=username).first().user
    if not user:
        return HTTPNotFound('No such user')
    submitted = DBSession.query(Review).filter_by(owner=user).order_by(Review.updated).all()
    reviews = (DBSession.query(ReviewVote)
                        .filter_by(owner=user)
                        .join(ReviewVote.review)
                        .filter(Review.owner != user)
                        .group_by(Review).order_by(Review.updated)).all()

    return dict(user=user, reviews=reviews, submitted=submitted)
