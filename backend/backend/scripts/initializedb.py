import os
import sys
import transaction

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from pyramid.scripts.common import parse_vars

from ..models import (
    DBSession,
    ReviewCategory,
    Source,
    Base,
    Review,
    )


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri> [var=value]\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) < 2:
        usage(argv)
    config_uri = argv[1]
    options = parse_vars(argv[2:])
    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=options)
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.create_all(engine)
    with transaction.manager:
        DBSession.add(Source(name='Github', slug='gh'))
        DBSession.add(Source(name='git', slug='git'))
        DBSession.add(Source(name='Launchpad', slug='lp'))
        DBSession.add(ReviewCategory(slug='charm', name='Charm'))
        DBSession.add(ReviewCategory(slug='tool', name='tool'))
        DBSession.add(ReviewCategory(slug='documentation', name='documentation'))
        DBSession.add(ReviewCategory(slug='askubuntu', name='Ask Ubuntu'))

#    with transaction.manager:
#        r = Review(title='New charm apache2', url='http://marcoceppi.com',
#                   type='NEW')
#        r.source = DBSession.query(Source).filter_by(slug='lp').one()
#        r.category = DBSession.query(ReviewCategory).filter_by(slug='charm').one()
#
#        DBSession.add(r)
#
#    with transaction.manager:
#        r = Review(title='Charmtools v 0.9.9.9', url='http://marcoceppi.com',
#                   type='UPDATE')
#        r.source = DBSession.query(Source).filter_by(slug='lp').one()
#        r.category = DBSession.query(ReviewCategory).filter_by(slug='tool').one()
#
#        DBSession.add(r)
#
#    with transaction.manager:
#        r = Review(title='Update mysql from crashed disk', url='http://marcoceppi.com',
#                   type='UPDATE')
#        r.source = DBSession.query(Source).filter_by(slug='lp').one()
#        r.category = DBSession.query(ReviewCategory).filter_by(slug='charm').one()
#
#        DBSession.add(r)

