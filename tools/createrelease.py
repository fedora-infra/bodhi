import click
import transaction

from pyramid.paster import bootstrap
from bodhi.config import get_configfile
from bodhi.models import Release


@click.command()
@click.option('--name', help='Release name (eg: F20)')
@click.option('--long-name', help='Long release name (eg: "Fedora 20")')
@click.option('--id-prefix', help='Release prefix (eg: FEDORA-EPEL)')
@click.option('--version', help='Release version number (eg: 20)')
@click.option('--dist-tag', help='Koji dist tag (eg: dist-5E-epel)')
def create_release(**kwargs):
    env = bootstrap(get_configfile())
    db = env['request'].db
    with transaction.manager:
        release = Release(**kwargs)
        db.add(release)
        print(release)


if __name__ == '__main__':
    create_release()
