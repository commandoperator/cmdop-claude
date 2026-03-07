import click

@click.group()
def cli(): pass

@cli.command()
def run():
    click.echo('Hello')

if __name__ == '__main__':
    cli()
