#!/usr/bin/python
"""
Print out a list of builds that need signing.
"""

__requires__ = 'bodhi'

import pkg_resources
import os
import sys
import pickle

import optparse

from fedora.client import BodhiClient

bodhi = BodhiClient(base_url='http://localhost/updates/')


parser = optparse.OptionParser()
parser.add_option('-e', '--epel',    action='store_true', help='Output EPEL builds')
parser.add_option('-f', '--fedora',  action='store_true', help='Output Fedora builds')
parser.add_option('-v', '--verbose', action='store_true', help='Verbose output')
opts, args = parser.parse_args()


def signable_builds(release):
    locked = set()

    # Load the bodhi masher state
    lock = '/mnt/koji/mash/updates/MASHING-%s' % release.id_prefix
    if os.path.exists(lock):
        state = pickle.load(file(lock))
        for update in state['updates']:
            for build in update.split(','):
                locked.add(build)

    for req in ('stable', 'testing'):
        updates = bodhi.query(request=req, release=release['name'])
        for update in updates['updates']:
            for build in update['builds']:
                if build['nvr'] not in locked:
                    yield build['nvr']

if __name__ == '__main__':
    for release in bodhi.get_releases()['releases']:

        if opts.verbose:
            print("release: %s" % release)

        if opts.epel and release['id_prefix'] == 'FEDORA-EPEL':
            pass
        elif opts.fedora and release['id_prefix'] == 'FEDORA':
            pass
        else:
            continue

        for build in signable_builds(release):
            print(build)

# vim: ts=4 sw=4 ai expandtab