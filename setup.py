import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    'pyramid',
    'pyramid_chameleon',
    'pyramid_debugtoolbar',
    'pyramid_tm',
    'SQLAlchemy',
    'transaction',
    'zope.sqlalchemy',
    'waitress',
    'launchpadlib',
    'alembic',
    'marshmallow',
    'python-dateutil',
    'velruse',
    'requests',
    'celery[redis]',
    'psycopg2',
    ]

setup(name='reviewq',
      version='1.6.0',
      description='Juju Ecosystem Review Queue',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web wsgi bfg pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='reviewq',
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = reviewq:main
      [console_scripts]
      initialize_backend_db = reviewq.scripts.initializedb:main
      initialize_lp_creds = reviewq.helpers:login
      ingest_the_world = reviewq.tasks:import_from_lp
      """,
      )
