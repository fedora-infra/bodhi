import click
import transaction

from pyramid.paster import bootstrap
from bodhi.config import get_configfile
from bodhi.models import Release


@click.command()
@click.option('--name', help='Release name (eg: F20)')
@click.option('--long-name', help='Long release name (eg: "Fedora 20")')
@click.option('--id-prefix', help='Release prefix (eg: FEDORA)')
@click.option('--version', help='Release version number (eg: 20)')
@click.option('--dist-tag', help='Koji dist tag (eg: dist-5E-epel)')
@click.option('--branch', help='Git branch name (eg: f20)')
def create_release(**kwargs):
    env = bootstrap(get_configfile())
    db = env['request'].db

    dist_tag = kwargs['dist_tag']
    kwargs['stable_tag'] = "%s-updates" % dist_tag
    kwargs['testing_tag'] = "%s-updates-testing" % dist_tag
    kwargs['candidate_tag'] = "%s-updates-candidate" % dist_tag
    kwargs['pending_testing_tag'] = "%s-updates-testing-pending" % dist_tag
    kwargs['pending_stable_tag'] = "%s-updates-pending" % dist_tag
    kwargs['override_tag'] = "%s-override" % dist_tag

    with transaction.manager:
        release = Release(**kwargs)
        db.add(release)
        print(release)


if __name__ == '__main__':
    create_release()
