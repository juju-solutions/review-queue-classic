from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from pyramid.events import subscriber
from pyramid.events import BeforeRender

from .models import (
    DBSession,
    Base,
    )


@subscriber(BeforeRender)
def add_global(event):
    import pkg_resources
    event['version'] = pkg_resources.get_distribution("backend").version


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    config = Configurator(settings=settings)
    config.include('pyramid_chameleon')
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('home', '/')
    config.add_route('find_user', '/user/+me')
    config.add_route('search_user', '/user/+search')
    config.add_route('id_user', '/user/id/{id}')
    config.add_route('view_user', '/user/{username}')
    config.add_route('show_review', '/review/{review}')
    config.add_route('show_reviews', '/reviews/{review}')
    config.add_route('query', '/search')
    config.add_route('query_results', '/search/{filter}')
    config.scan()
    return config.make_wsgi_app()
