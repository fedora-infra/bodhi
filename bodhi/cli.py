import click
import pprint

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
@click.option('--close-bugs', help='Automatically close bugs')
@click.option('--request', help='Requested repository',
              type=click.Choice(['testing', 'stable', 'unpush']))
@click.option('--autokarma', default=True, help='Enable karma automatism')
@click.option('--stable-karma', help='Stable karma threshold')
@click.option('--unstable-karma', help='Unstable karma threshold')
@click.option('--suggest', help='Post-update user suggestion',
              type=click.Choice(['logout', 'reboot']))
def new(username, password, **kwargs):
    client = BodhiClient()
    client.login(username, password)
    resp = client.new(**kwargs)
    if resp.status_code == 200:
        data = resp.json()
        click.echo(pprint.pformat(data))
    else:
        click.echo(resp.text)


if __name__ == '__main__':
    cli()
