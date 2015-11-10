import logging

from dateutil import parser

from datetime import (
    datetime,
    timedelta,
)

from pyramid.httpexceptions import (
    HTTPFound,
    HTTPNotFound,
    HTTPUnauthorized,
)

from pyramid.view import view_config

from .models import (
    DBSession,
    Review,
    Profile,
    User,
    ReviewVote,
    ReviewTest,
)

from .helpers import (
    UserSerializer,
    ReviewSerializer,
    ReviewedSerializer,
    ReviewTestSerializer,
    get_lp,
    create_user,
)


from tasks import update_lp_item


log = logging.getLogger(__name__)


@view_config(route_name='home', accept='text/html',
             renderer='templates/dashboard.pt')
def dashboard(request):
    reviews = DBSession.query(Review).filter(
        Review.state != 'REVIEWED',
        Review.state != 'NEW',
        Review.state != 'IN PROGRESS',
        Review.state != 'CLOSED',
        Review.state != 'MERGED',
        Review.state != 'ABANDONDED').order_by(
        Review.updated).all()

    incoming = DBSession.query(Review).filter_by(
        state='NEW').order_by(Review.updated).all()

    return dict(reviews=reviews, incoming=incoming)


@view_config(route_name='home', accept='application/json', renderer='json')
def dashboard_json(req):
    d = dashboard(req)
    return {
        'reviews': [ReviewSerializer().dump(r).data for r in d['reviews']],
        'incoming': [ReviewSerializer().dump(r).data for r in d['incoming']],
    }


@view_config(route_name='find_user', renderer='templates/user.pt')
def find_user(req):
    if 'User' not in req.session:
        return HTTPFound(location='/login/openid')

    req.matchdict['username'] = req.session['User'].profiles[0].username
    return user(req)


@view_config(route_name='search_user', renderer='json')
def search_user(req):
    query = req.params['q']
    matches = DBSession.query(User).filter(
        User.name.like('%%%s%%' % query)).all()
    return UserSerializer(
        many=True, exclude=('reviews',)
    ).dump(matches).data


@view_config(route_name='query_results', renderer='templates/search.pt')
def saved_search(request):
    # q = request.matchdict['filter']
    # return search(request, q)
    return {}


@view_config(route_name='login', renderer='json')
def login(req):
    mode = req.params.get('openid.mode')
    log.debug('mode: %s' % mode)

    if mode == 'cancel':
        log.debug('User canceled. Why? Who cares')
        return HTTPFound(location=req.route_url('home'))

    if mode == 'id_res':
        claimed = req.params.get('openid.claimed_id')
        username = req.params.get('openid.sreg.nickname')

        profile = DBSession.query(Profile).filter_by(claimed=claimed).first()

        if not profile:
            log.debug('Never logged in before? Welcome.')
            # So, first time login. Try to match username?
            profile = DBSession.query(Profile).filter_by(
                username=username).first()

        if profile:
            user = profile.user

        if not profile:
            log.debug('Fuck off, you havent done jack shit')
            # Okay, so we still don't have a profile. wtf guys.
            # GET YOUR REVIEW ON. Create a user for now? Sure.
            lp = get_lp()
            person = lp.load('{}/~{}'.format(
                req.registry.settings['launchpad.api.url'], username))
            user = create_user(person)
            profile = user.profile[0]

        if not profile.claimed:
            profile.claimed = claimed

    req.session['user'] = user.id
    return HTTPFound(location=req.route_url('home'))


@view_config(route_name='query', renderer='templates/search.pt')
def search(request):
    filters = {
        'reviewer': [],
        'owner': [],
        'from': None,
        'to': None,
        'source': None,
        'state': [],
    }
    if not request.params:
        week_ago = datetime.now() - timedelta(days=7)
        filters['from'] = week_ago.strftime("%Y-%m-%d %H:%M")
        return dict(results=None, filters=filters)

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
    if filters['from']:
        td = parser.parse(filters['from'])
        q = q.filter(Review.updated >= td)
    if filters['to']:
        td = parser.parse(filters['to'])
        q = q.filter(Review.updated <= td)
    if filters['reviewer']:
        if not isinstance(filters['reviewer'], list):
            filters['reviewer'] = [filters['reviewer']]
        q = (q.join(ReviewVote.review)
              .filter(ReviewVote.user_id.in_(filters['reviewer'])))

    data = q.order_by(Review.updated).all()
    return dict(results=data, filters=filters)


@view_config(route_name='lock_review', renderer='json')
def lock_review(request):
    if 'User' not in request.session:
        return dict(error='Not logged in')

    review_id = request.matchdict['review']
    review = DBSession.query(Review).get(review_id)
    user = request.session['User']

    if not review:
        return dict(error='Unable to find review %s' % review_id)

    if review.locked:
        if review.locker != user:
            return dict(
                error='Review already locked by: %s' % review.locker.name)

        review.unlock()
        return dict(error=None)

    review.lock(user)
    return dict(error=None)


@view_config(route_name='test_review')
def test_review(request):
    user = request.session.get('User')
    if not (user and user.is_charmer):
        return HTTPUnauthorized()

    review = Review.get(request.matchdict['review'])
    if not review:
        return HTTPNotFound()

    substrate = request.params.get('substrate')
    substrate = (
        request.registry.settings['testing.substrates'].split(',')
        if substrate == 'all'
        else [substrate]
    )

    review.create_tests(
        request.registry.settings, substrates=substrate)

    return HTTPFound(location=request.route_url(
        'show_review', review=review.id))


@view_config(route_name='show_review', accept='text/html',
             renderer='templates/review.pt')
def review(req):
    review_id = req.matchdict['review']
    review = DBSession.query(Review).filter_by(id=review_id).first()

    if not review:
        return HTTPNotFound('No such review')

    settings = req.registry.settings
    substrates = settings.get('testing.substrates', '')
    substrates = [s.strip() for s in substrates.split(',')]
    return dict(
        review=review,
        substrates=substrates,
    )


@view_config(route_name='show_review', accept='application/json',
             renderer='json')
def review_json(req):
    return ReviewSerializer().dump(review(req)['review']).data


@view_config(route_name='id_user', accept="application/json", renderer='json')
def id_json(request):
    data = DBSession.query(User).get(request.matchdict['id'])
    return UserSerializer(exclude=('reviews', )).dump(data).data


@view_config(route_name='view_user', accept="application/json",
             renderer='json')
def user_json(request):
    data = user(request)

    return dict(
        user=UserSerializer(
            exclude=('reviews',)).dump(data['user']).data,
        reviews=ReviewedSerializer(
            many=True).dump(data['reviews']).data,
        submitted=ReviewSerializer(
            exclude=('owner', ), many=True).dump(data['submitted']).data,
    )


@view_config(route_name='view_user',
             accept="text/html",
             renderer='templates/user.pt')
def user(request):
    username = request.matchdict['username']
    user = DBSession.query(Profile).filter_by(username=username).first().user
    if not user:
        return HTTPNotFound('No such user')
    submitted = (
        DBSession.query(Review)
        .filter_by(owner=user)
        .order_by(Review.updated)
        .all()
    )
    reviews = (
        DBSession.query(Review)
        .filter(
            Review.id.in_(
                DBSession.query(Review.id)
                .join(ReviewVote)
                .filter_by(owner=user)),
            Review.owner != user)
        .order_by(Review.updated)
        .all()
    )
    locked = (
        DBSession.query(Review)
        .filter_by(locker=user)
        .order_by(Review.locked)
        .all()
    )

    return dict(user=user, reviews=reviews, submitted=submitted, locked=locked)


@view_config(route_name='cbt_review_callback', renderer='json')
def cbt_processing(request):
    review_id = request.matchdict.get('review_id')
    review_test_id = request.matchdict.get('review_test_id')
    if review_id and review_test_id:
        rt = ReviewTest.get(int(review_test_id))

    if not rt:
        return HTTPNotFound('ReviewTest not found')

    rt.status = request.params.get('status')
    rt.url = request.params.get('build_url')
    if rt.status != 'RUNNING':
        rt.finished = datetime.utcnow()
        update_lp_item.delay(rt)

    return ReviewTestSerializer().dump(rt).data
