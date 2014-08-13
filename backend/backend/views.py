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
    )


@view_config(route_name='home', renderer='templates/dashboard.pt')
def dashboard(request):
    #reviews = DBSession.query(Review).group_by(Review.review_category_id).all()
    reviews = DBSession.query(Review).order_by(Review.updated).all()

    for review in reviews:
        b = date.fromtimestamp(review.updated) - date.today()
        review.age = b.days

    return dict(reviews=reviews)
