from pathlib import Path
from time import sleep

import click
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from bagels.locations import config_file, database_file, set_custom_root
from bagels.versioning import get_current_version, get_pypi_version, needs_update


@click.group(invoke_without_command=True)
@click.option(
    "--at",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
    help="Specify the path.",
)
@click.option(
    "--migrate",
    type=click.Choice(["actualbudget"]),
    help="Specify the migration type.",
)
@click.option(
    "--source",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    help="Path to source database file for migration.",
)
@click.pass_context
def cli(ctx, at: Path | None, migrate: str | None, source: Path | None):
    """Bagels CLI."""
    if at:
        set_custom_root(at)

    if migrate:
        if not source:
            raise click.UsageError("--source is required when using --migrate")

        if migrate == "actualbudget":
            try:
                click.echo(f"Starting migration from {source}")
                from bagels.models.database.app import init_db

                init_db()

                from bagels.locations import database_file
                from bagels.migrations.migrate_actualbudget import (
                    BudgetToBagelsMigration,
                )

                migrator = BudgetToBagelsMigration(str(source), str(database_file()))
                migrator.migrate()
                click.echo(click.style("Migration completed successfully!", fg="green"))
                return
            except Exception as e:
                click.echo(click.style(f"Migration failed: {str(e)}", fg="red"))
                ctx.exit(1)

    if ctx.invoked_subcommand is None:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task(f"Loading configuration from '{at}'...", total=3)

            from bagels.config import load_config

            load_config()

            from bagels.config import CONFIG

            if CONFIG.state.check_for_updates:
                progress.update(task, advance=1, description="Checking for updates...")

                if needs_update():
                    new = get_pypi_version()
                    cur = get_current_version()
                    click.echo(
                        click.style(
                            f"New version available ({cur} -> {new})! Update with:",
                            fg="yellow",
                        )
                    )
                    click.echo(click.style("```uv tool upgrade bagels```", fg="cyan"))
                    click.echo(
                        click.style(
                            "You can disable this check in-app using the command palette.",
                            fg="bright_black",
                        )
                    )
                    sleep(2)

            progress.update(task, advance=1, description="Initializing database...")

            from bagels.models.database.app import init_db

            init_db()

            # Best-effort prefetch for smoother multicurrency totals.
            try:
                from bagels.config import CONFIG as CURRENT_CONFIG
                from bagels.managers.accounts import get_all_accounts
                from bagels.managers.currency import warm_rates_for_currencies

                accounts = get_all_accounts(get_hidden=True)
                warm_rates_for_currencies(
                    currencies=[
                        getattr(account, "currencyCode", None) for account in accounts
                    ],
                    target_currency=CURRENT_CONFIG.state.currency.main_currency,
                )
            except Exception:
                pass

            progress.update(task, advance=1, description="Starting application...")

            from bagels.app import App

            app = App()
            progress.update(task, advance=1)

        app.run()


@cli.command()
@click.argument("thing_to_locate", type=click.Choice(["config", "database"]))
def locate(thing_to_locate: str) -> None:
    if thing_to_locate == "config":
        print("Config file:")
        print(config_file())
    elif thing_to_locate == "database":
        print("Database file:")
        print(database_file())


if __name__ == "__main__":
    cli()
