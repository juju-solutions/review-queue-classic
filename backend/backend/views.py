import re

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
    reviews = DBSession.query(Review).group_by(Review.review_category_id).all()

    return dict(reviews=reviews)
