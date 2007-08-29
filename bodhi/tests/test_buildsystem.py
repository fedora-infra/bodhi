# $Id: $

import turbogears
from turbogears import testutil, config
turbogears.update_config(configfile='dev.cfg', modulename='bodhi.config')

class TestBuildsystem(testutil.DBTest):

    def test_valid_buildsys(self):
        buildsys = config.get('buildsystem')
        assert buildsys == 'koji' or buildsys == 'dev'

    def test_session(self):
        from bodhi.buildsys import get_session
        session = get_session()
        assert session
