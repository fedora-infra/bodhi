import click

from bodhi.client import BodhiClient


@click.group()
def cli():
    pass


@cli.command()
@click.argument('builds')
@click.option('--username', envvar='USERNAME')
@click.option('--password', prompt=True, hide_input=True)
@click.option('--type', default='bugfix', help='Update type', required=True,
              type=click.Choice(['security', 'bugfix',
                                 'enhancement', 'newpackage']))
@click.option('--notes', help='Update description')
@click.option('--bugs', help='Comma-seperated list of bug numbers')
@click.option('--close-bugs', default=True, is_flag=True, help='Automatically close bugs')
@click.option('--request', help='Requested repository',
              type=click.Choice(['testing', 'stable', 'unpush']))
@click.option('--autokarma', default=True, is_flag=True, help='Enable karma automatism')
@click.option('--stable-karma', help='Stable karma threshold')
@click.option('--unstable-karma', help='Unstable karma threshold')
@click.option('--suggest', help='Post-update user suggestion',
              type=click.Choice(['logout', 'reboot']))
def new(username, password, **kwargs):
    client = BodhiClient()
    client.login(username, password)
    resp = client.new(**kwargs)
    print_resp(resp)


@cli.command()
@click.option('--approved-since', help='Approved after a specific timestamp')
@click.option('--modified-since', help='Modified after a specific timestamp')
@click.option('--bugs', help='A list of bug numbers')
@click.option('--critpath', is_flag=True, default=None,
              help='Query only critical path packages')
@click.option('--cves', help='Query by CVE id')
@click.option('--packages', help='Query by package name(s)')
@click.option('--pushed', is_flag=True, default=None,
              help='Filter by pushed updates')
@click.option('--pushed-since',
              help='Updates that have been pushed after a certain time')
@click.option('--releases', help='Updates for specific releases')
@click.option('--locked', help='Updates that are in a locked state')
@click.option('--request', help='Updates with a specific request',
              type=click.Choice(['testing', 'stable', 'unpush']))
@click.option('--submitted-since',
              help='Updates that have been submitted since a certain time')
@click.option('--status', help='Filter by update status',
              type=click.Choice(['pending', 'testing', 'stable', 'obsolete',
                                 'unpushed', 'processing']))
@click.option('--suggest', help='Filter by post-update user suggestion',
              type=click.Choice(['logout', 'reboot']))
@click.option('--type', default='bugfix', help='Filter by update type',
              type=click.Choice(['newpackage', 'security',
                                 'bugfix', 'enhancement',]))
@click.option('--user', help='Updates submitted by a specific user')
def query(**kwargs):
    client = BodhiClient()
    resp = client.query(**kwargs)
    print_resp(resp)


def print_resp(resp):
    if resp.status_code == 200:
        try:
            data = resp.json()
            click.echo(data)
        except ValueError:
            click.echo('Unable to decode JSON:')
            click.echo(resp.text)
    else:
        click.echo(resp.text)


if __name__ == '__main__':
    cli()
