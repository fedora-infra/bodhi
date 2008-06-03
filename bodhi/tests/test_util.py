import os
import yum
import tempfile

from os.path import exists, join
from turbogears import config, update_config
from bodhi.util import Singleton, sanity_check_repodata, mkmetadatadir

import logging
log = logging.getLogger(__name__)

update_config(configfile='bodhi.cfg', modulename='bodhi.config')

class TestUtil:

    def test_singleton(self):
        """ Make sure our Singleton class actually works """
        class A(Singleton):
            pass
        a = A()
        assert a
        b = A()
        assert b is a

    def test_acls(self):
        acl = config.get('acl_system')
        assert acl in ('dummy', 'pkgdb'), "Unknown acl system: %s" % acl

    def test_sanity_check_repodata(self):
        """
        Do an extremely basic check to make sure that the
        sanity_check_repodata code actually runs.  This is by no means 
        a complete test for all possible forms of repodata corruption.
        """
        ## Initialize our temporary repo
        temprepo = tempfile.mkdtemp('bodhi')
        mkmetadatadir(temprepo)

        ## Verify sanity
        sanity_check_repodata(temprepo)

        ## Corrupt metadata
        os.system('echo 1 >> %s' % join(temprepo, 'repodata', 'repomd.xml'))

        # verify insanity
        try:
            sanity_check_repodata(temprepo)
            assert False, "Damaged repomd.xml not detected!"
        except yum.Errors.RepoMDError, e:
            assert e.value == "Damaged repomd.xml file"
