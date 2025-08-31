"""CodeScribe AI: A tool for AI-assisted project documentation."""
import click
from .config import load_config
from .llm_handler import LLMHandler
from .orchestrator import DocstringOrchestrator
from .readme_generator import ReadmeGenerator

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.pass_context
def cli(ctx):
    """CodeScribe AI: A tool for AI-assisted project documentation.

Choose a command below (e.g., 'docstrings', 'readmes') and provide its options."""
    ctx.ensure_object(dict)
    try:
        config = load_config()
        if not config.api_keys:
            raise click.UsageError('No API keys found in the .env file. Please create one.')
        ctx.obj['LLM_HANDLER'] = LLMHandler(config.api_keys)
        click.echo(f'Initialized with {len(config.api_keys)} API keys.')
    except Exception as e:
        raise click.ClickException(f'Initialization failed: {e}')

@cli.command()
@click.option('--path', required=True, help='The local path or Git URL of the project.')
@click.option('--desc', required=True, help='A short description of the project.')
@click.option('--exclude', multiple=True, help='Directory/regex pattern to exclude. Can be used multiple times.')
@click.pass_context
def docstrings(ctx, path, desc, exclude):
    """Generates Python docstrings for all files."""
    click.echo('\n--- Starting Docstring Generation ---')
    llm_handler = ctx.obj['LLM_HANDLER']
    orchestrator = DocstringOrchestrator(path_or_url=path, description=desc, exclude=list(exclude), llm_handler=llm_handler)
    try:
        orchestrator.run()
        click.secho('Successfully generated all docstrings.', fg='green')
    except Exception as e:
        click.secho(f'An error occurred during docstring generation: {e}', fg='red')

@cli.command()
@click.option('--path', required=True, help='The local path or Git URL of the project.')
@click.option('--desc', required=True, help='A short description of the project.')
@click.option('--exclude', multiple=True, help='Directory/regex pattern to exclude. Can be used multiple times.')
@click.pass_context
def readmes(ctx, path, desc, exclude):
    """Generates README.md files for each directory."""
    click.echo('\n--- Starting README Generation ---')
    llm_handler = ctx.obj['LLM_HANDLER']
    generator = ReadmeGenerator(path_or_url=path, description=desc, exclude=list(exclude), llm_handler=llm_handler)
    try:
        generator.run()
        click.secho('Successfully generated all README files.', fg='green')
    except Exception as e:
        click.secho(f'An error occurred during README generation: {e}', fg='red')

def main():
    """No docstring provided."""
    cli(obj={})
if __name__ == '__main__':
    main()