import re

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
    )


@view_config(route_name='home', renderer='templates/dashboard.pt')
def dashboard(request):
    #reviews = DBSession.query(Review).group_by(Review.review_category_id).all()
    reviews = DBSession.query(Review).filter(Review.state != 'REVIEWED', Review.state != 'NEW', Review.state != 'IN PROGRESS').order_by(Review.updated).all()
    incoming = DBSession.query(Review).filter_by(state='NEW').order_by(Review.updated).all()
    return dict(reviews=reviews, incoming=incoming)


@view_config(route_name='view_user', renderer='templates/user.pt')
def user(request):
    username = request.matchdict['username']
    user = DBSession.query(Profile).filter_by(username=username).first().user
    if not user:
        return HTTPNotFound('No such user')

    return dict(user=user)
