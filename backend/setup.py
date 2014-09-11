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
    ]

setup(name='backend',
      version='1.4.0',
      description='backend',
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
      test_suite='backend',
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = backend:main
      [console_scripts]
      initialize_backend_db = backend.scripts.initializedb:main
      initialize_lp_creds = backend.helpers:login
      ingest_the_world = backend.tasks:import_from_lp
      """,
      )
