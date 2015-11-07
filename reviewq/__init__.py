from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory

from sqlalchemy import engine_from_config
from ubuntusso import add_ubuntu_login

from .models import (
    DBSession,
    Base,
)


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    session_factory = SignedCookieSessionFactory('whateve', timeout=7200)

    config = Configurator(settings=settings)
    config.set_session_factory(session_factory)
    config.include('pyramid_chameleon')
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('home', '/')
    config.add_route('find_user', '/user/+me')
    config.add_route('login', '/login/openid/callback')
    config.add_route('search_user', '/user/+search')
    config.add_route('id_user', '/user/id/{id}')
    config.add_route('view_user', '/user/{username}')
    config.add_route('lock_review', '/review/{review}/lock')
    config.add_route(
        'cbt_review_callback',
        '/review/{review_id}/ctb_callback/{review_test_id}')
    config.add_route('test_review', '/review/{review}/test')
    config.add_route('show_review', '/review/{review}')
    config.add_route('query', '/search')
    config.add_route('query_results', '/search/{filter}')
    config.scan()
    add_ubuntu_login(config)

    return config.make_wsgi_app()
