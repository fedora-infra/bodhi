# $Id: $

import turbogears
turbogears.update_config(configfile='bodhi.cfg', modulename='bodhi.config')

class TestMasher:

    def test_repo_tag(self):
        from bodhi.util import get_repo_tag
        assert get_repo_tag('f7-updates') == 'dist-fc7-updates'
        assert get_repo_tag('f7-updates-testing') == 'dist-fc7-updates-testing'
