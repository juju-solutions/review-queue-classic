import os
import imp
import glob
import inspect
import logging

from sqlalchemy import engine_from_config

from .helpers import (
    get_lp,
)

from .models import (
    DBSession,
)

from pyramid.paster import (
    get_appsettings,
    setup_logging,
)


setup_logging('%s.ini' % os.environ.get('ENV', 'development'))
logger = logging.getLogger(__file__)


def is_source(o):
    return inspect.isclass(o) and issubclass(o, SourcePlugin)


class SourcePlugin(object):
    def __init__(self, lp=None, log=None):
        if not log:
            log = logger

        self.logger = log
        self.log = self.logger.info

        if not lp:
            lp = get_lp()

        self.lp = lp


class PluginManager(object):
    def __init__(self, plugin_dirs=None):
        self.cfg = {}
        self.plugin_dirs = plugin_dirs
        self.plugins = {}

        if plugin_dirs:
            if not os.path.exists(plugin_dirs):
                raise ValueError('%s does not exist' % plugin_dirs)

            self.load_plugins(plugin_dirs)

    def load_plugins(self, plugin_dir):
        files = glob.glob(os.path.join(plugin_dir, '*.py'))
        for f in files:
            plugin_name = os.path.splitext(os.path.basename(f))[0]
            if plugin_name.startswith('_'):
                continue

            plugin = imp.load_source(plugin_name, f)
            cls = inspect.getmembers(plugin, predicate=is_source).pop()
            if cls:
                cls = cls[1]
                self.plugins[plugin_name] = cls()

    def get_plugin(self, name):
        return self.plugins[name] if self.is_plugin(name) else None

    def is_plugin(self, name):
        return name in self.plugins
