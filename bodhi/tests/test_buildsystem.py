# $Id: $

import turbogears
from turbogears import testutil, config, database

turbogears.update_config(configfile='bodhi.cfg', modulename='bodhi.config')
database.set_db_uri("sqlite:///:memory:")

class TestBuildsystem(testutil.DBTest):

    def test_valid_buildsys(self):
        buildsys = config.get('buildsystem')
        assert buildsys in ('koji', 'dev')

    def test_session(self):
        from bodhi.buildsys import get_session
        session = get_session()
        assert session
