import os
import logging

from pyramid.paster import get_appsettings

log = logging.getLogger('bodhi')


def get_configfile():
    configfile = None
    setupdir = os.path.dirname(os.path.dirname(__file__))
    if configfile:
        if not os.path.exists(configfile):
            log.error("Cannot find config: %s" % configfile)
            return
    else:
        for cfg in (os.path.join(setupdir, 'development.ini'),
                    '/etc/bodhi/production.ini'):
            if os.path.exists(cfg):
                configfile = cfg
                break
        else:
            log.error("Unable to find configuration to load!")
    return configfile


class BodhiConfig(dict):
    loaded = False

    def __getitem__(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).__getitem__(*args, **kw)

    def get(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).get(*args, **kw)

    def load_config(self):
        configfile = get_configfile()
        self.update(get_appsettings(configfile))
        self.loaded = True


config = BodhiConfig()
