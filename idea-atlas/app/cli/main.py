"""IDEA Atlas command-line interface.

Every command that writes to the database runs inside a single transaction and
prints what it did. Commands that would reach the network refuse to run against
unverified source URLs unless explicitly forced -- the manifest's ``url_verified``
flag is a gate, not a comment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from app import __version__
from app.core.config import PROJECT_ROOT, get_settings
from app.core.enums import CrawlStatus, IngestionStatus
from app.core.logging import configure_logging

app = typer.Typer(
    name="idea-atlas",
    help="Legal information infrastructure for the IDEA.",
    no_args_is_help=True,
    add_completion=False,
)
db_app = typer.Typer(name="db", help="Database migrations.", no_args_is_help=True)
app.add_typer(db_app)

console = Console()
err_console = Console(stderr=True)


def _alembic_config() -> object:
    from alembic.config import Config

    return Config(str(PROJECT_ROOT / "alembic.ini"))


@app.callback()
def _root() -> None:
    """Configure logging before any command runs."""
    configure_logging(get_settings())


@app.command()
def version() -> None:
    """Print the version and resolved environment."""
    settings = get_settings()
    console.print(f"idea-atlas {__version__}")
    console.print(f"environment: {settings.env}")
    console.print(f"database:    {str(settings.sqlalchemy_url).split('@')[-1]}")
    console.print(f"ai provider: {settings.ai_provider}")


@db_app.command("upgrade")
def db_upgrade(revision: str = typer.Argument("head")) -> None:
    """Apply migrations up to REVISION (default: head)."""
    from alembic import command

    command.upgrade(_alembic_config(), revision)  # type: ignore[arg-type]
    console.print(f"[green]migrations applied to {revision}[/green]")


@db_app.command("downgrade")
def db_downgrade(revision: str = typer.Argument(...)) -> None:
    """Revert migrations down to REVISION."""
    from alembic import command

    command.downgrade(_alembic_config(), revision)  # type: ignore[arg-type]
    console.print(f"[yellow]migrations reverted to {revision}[/yellow]")


@db_app.command("current")
def db_current() -> None:
    """Show the applied migration revision."""
    from alembic import command

    command.current(_alembic_config(), verbose=True)  # type: ignore[arg-type]


@app.command()
def seed(
    reference_only: Annotated[
        bool, typer.Option("--reference-only", help="Skip demo propositions.")
    ] = False,
) -> None:
    """Seed jurisdictions, the IDEA taxonomy, and the federal source registry.

    Idempotent: re-running only inserts what is missing.
    """
    from app.db.session import session_scope
    from app.services.seed import seed_demo_propositions, seed_reference_data

    with session_scope() as session:
        counts = seed_reference_data(session)
        console.print(f"[green]reference data:[/green] {counts}")

        if not reference_only:
            created, links = seed_demo_propositions(session)
            counts.propositions, counts.proposition_links = created, links
            if created:
                console.print(
                    f"[green]demo propositions:[/green] {created} (with {links} authority links)"
                )
                console.print(
                    "[yellow]note:[/yellow] demo propositions are review_status="
                    "needs_review and are NOT served by /v1/research by default."
                )
            else:
                console.print(
                    "[yellow]demo propositions: none created[/yellow] - "
                    "run `idea-atlas ingest-source ecfr-34-cfr-300 --fixtures` first "
                    "so the cited authorities exist."
                )


@app.command("ingest-source")
def ingest_source(
    source_slug: Annotated[str, typer.Argument(help="Registered source slug.")],
    fixtures: Annotated[
        bool,
        typer.Option("--fixtures", help="Ingest from local fixtures instead of network."),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report changes without writing versions.")
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Allow live ingestion from unverified URLs."),
    ] = False,
) -> None:
    """Run the ingestion pipeline for one registered source."""
    from sqlalchemy import select

    from app.db.session import session_scope
    from app.ingestion.fixtures import load_fixture_collector
    from app.ingestion.pipeline import IngestionPipeline
    from app.models import Source

    with session_scope() as session:
        source = session.scalars(select(Source).where(Source.slug == source_slug)).one_or_none()
        if source is None:
            err_console.print(f"[red]no registered source with slug {source_slug!r}[/red]")
            err_console.print("run `idea-atlas seed` first, or check `verify-sources`.")
            raise typer.Exit(code=1)

        if fixtures:
            fixture_slug, collector = load_fixture_collector()
            if fixture_slug != source_slug:
                err_console.print(
                    f"[red]fixture set targets {fixture_slug!r}, not {source_slug!r}[/red]"
                )
                raise typer.Exit(code=1)
        else:
            if source.crawl_status is not CrawlStatus.URLS_VERIFIED and not force:
                err_console.print(
                    f"[red]refusing live ingestion:[/red] source {source_slug!r} has "
                    f"crawl_status={source.crawl_status.value}."
                )
                err_console.print(
                    "Verify its URL and set url_verified in the manifest, or pass "
                    "--force to override deliberately."
                )
                raise typer.Exit(code=2)
            err_console.print(
                "[red]live collectors are not implemented for this source yet.[/red] "
                "Use --fixtures, or implement a Collector. See docs/INGESTION.md."
            )
            raise typer.Exit(code=3)

        report = IngestionPipeline(session, actor="cli", dry_run=dry_run).run(source, collector)

    color = {
        IngestionStatus.COMPLETED: "green",
        IngestionStatus.PARTIAL: "yellow",
        IngestionStatus.FAILED: "red",
    }.get(report.status, "white")
    console.print(f"[{color}]status: {report.status.value}[/{color}]")
    console.print(
        f"seen={report.documents_seen} new={report.new_documents} "
        f"changed={report.changed_documents} unchanged={report.unchanged_documents} "
        f"errors={report.error_count}"
    )
    for error in report.errors:
        err_console.print(f"  [red]error:[/red] {error}")
    if fixtures:
        console.print(
            "[yellow]fixture data:[/yellow] stored versions are marked "
            "review_status=needs_review and synthetic_fixture=true."
        )
    if report.status is IngestionStatus.FAILED:
        raise typer.Exit(code=1)


@app.command("ingest-jurisdiction")
def ingest_jurisdiction(
    slug: Annotated[str, typer.Argument(help="Jurisdiction slug, e.g. nc.")],
) -> None:
    """Ingest every verified source for a jurisdiction.

    Reports honestly when a jurisdiction has no verified sources, which today is
    every jurisdiction except where a manifest has been filled in and confirmed.
    """
    from app.core.config import MANIFEST_DIR
    from app.legal.manifests import load_jurisdiction_manifest

    path = MANIFEST_DIR / "jurisdictions" / f"{slug.strip().lower()}.yaml"
    if not path.is_file():
        err_console.print(f"[red]no manifest for jurisdiction {slug!r}[/red]")
        raise typer.Exit(code=1)

    manifest = load_jurisdiction_manifest(path)
    actionable = {
        name: site for name, site in manifest.official_sites.items() if site.is_actionable
    }
    console.print(f"[bold]{manifest.jurisdiction_name}[/bold] ({manifest.jurisdiction})")
    console.print(f"  SEA: {manifest.sea or 'unknown'}")
    console.print(f"  declared sites: {manifest.declared_site_count}/8")
    console.print(f"  verified sites: {manifest.verified_site_count}/8")

    if not actionable:
        console.print(
            "[yellow]nothing to ingest:[/yellow] no official URL for this "
            "jurisdiction has been populated and verified."
        )
        console.print(f"Edit {path} and set verified: true on each confirmed URL.")
        raise typer.Exit(code=0)

    console.print(
        "[yellow]jurisdiction collectors are not implemented yet.[/yellow] "
        f"{len(actionable)} verified site(s) are ready: {', '.join(actionable)}"
    )
    console.print("See docs/INGESTION.md for how to add a collector.")


@app.command("verify-sources")
def verify_sources(
    live: Annotated[
        bool,
        typer.Option("--live", help="Actually fetch each URL to confirm it resolves."),
    ] = False,
) -> None:
    """Report which manifest URLs are declared and which are verified.

    Without ``--live`` this is a pure manifest audit and makes no network
    requests.
    """
    from app.legal.manifests import load_all_jurisdiction_manifests, load_federal_manifest

    federal = load_federal_manifest()
    table = Table(title="Federal sources", show_lines=False)
    table.add_column("slug")
    table.add_column("type")
    table.add_column("url verified", justify="center")
    table.add_column("copyright")
    for entry in federal.sources:
        table.add_row(
            entry.slug,
            entry.source_type.value,
            "[green]yes[/green]" if entry.url_verified else "[red]no[/red]",
            entry.copyright_status.value,
        )
    console.print(table)

    manifests = load_all_jurisdiction_manifests()
    declared = sum(m.declared_site_count for m in manifests)
    verified = sum(m.verified_site_count for m in manifests)
    possible = len(manifests) * 8
    console.print(
        f"\n[bold]Jurisdiction manifests:[/bold] {len(manifests)} files, "
        f"{declared}/{possible} sites declared, {verified}/{possible} verified"
    )
    if verified == 0:
        console.print(
            "[yellow]No jurisdiction URL has been verified yet.[/yellow] "
            "This is the accurate state, not a bug - see docs/JURISDICTIONS.md."
        )

    if live:
        _verify_live(federal)


def _verify_live(federal: object) -> None:
    """Fetch each federal base URL through the SSRF-safe validator."""
    from app.core.errors import IngestionError, UnsafeUrlError
    from app.ingestion.fetcher import DocumentFetcher
    from app.legal.manifests import FederalManifest

    if not isinstance(federal, FederalManifest):  # pragma: no cover - defensive
        raise TypeError(f"expected a FederalManifest, got {type(federal).__name__}")
    console.print("\n[bold]Live URL check[/bold] (requires outbound .gov access)")
    with DocumentFetcher() as fetcher:
        for entry in federal.sources:
            try:
                result = fetcher.fetch(entry.base_url)
            except UnsafeUrlError as exc:
                console.print(f"  [red]BLOCKED[/red] {entry.slug}: {exc}")
            except IngestionError as exc:
                console.print(f"  [yellow]UNREACHABLE[/yellow] {entry.slug}: {exc}")
            else:
                console.print(
                    f"  [green]OK[/green] {entry.slug}: HTTP {result.status_code}, "
                    f"{result.byte_size} bytes, {result.content_type}"
                )


@app.command("show-coverage")
def show_coverage(
    only_with_data: Annotated[
        bool, typer.Option("--only-with-data", help="Hide jurisdictions with no data.")
    ] = False,
) -> None:
    """Print the nationwide coverage table."""
    from app.db.session import session_scope
    from app.services.coverage import build_coverage_report

    with session_scope() as session:
        report = build_coverage_report(session)

    table = Table(title="IDEA Atlas coverage", show_lines=False)
    for column in (
        "Jurisdiction",
        "Statutes",
        "Regs",
        "Proc. safeguards",
        "SEA guidance",
        "Due process",
        "State complaints",
        "Federal cases",
        "Last checked",
        "Errors",
    ):
        table.add_column(column, overflow="fold")

    for row in report.rows:
        if only_with_data and row.total_authorities == 0:
            continue
        table.add_row(
            f"{row.name} ({row.slug})",
            row.display("statutes"),
            row.display("regulations"),
            row.display("procedural_safeguards"),
            row.display("sea_guidance"),
            row.display("due_process"),
            row.display("state_complaints"),
            row.display("federal_cases"),
            row.last_checked_at.strftime("%Y-%m-%d") if row.last_checked_at else "never",
            str(row.error_count),
        )
    console.print(table)
    console.print(
        f"{report.jurisdictions_with_any_data}/{report.total_jurisdictions} "
        f"jurisdictions have any ingested authority; "
        f"{report.jurisdictions_with_manifest} have a manifest."
    )


@app.command("run-api")
def run_api(
    host: str = typer.Option(None, help="Bind host (default from settings)."),
    port: int = typer.Option(None, help="Bind port (default from settings)."),
    reload: Annotated[bool, typer.Option("--reload", help="Auto-reload on change.")] = False,
) -> None:
    """Start the API server."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.api.main:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


@app.command("export-openapi")
def export_openapi(
    out: Annotated[Path, typer.Option(help="Output path.")] = Path("openapi.json"),
) -> None:
    """Write the OpenAPI schema to a file."""
    import json

    from app.api.main import create_app

    out.write_text(json.dumps(create_app().openapi(), indent=2), encoding="utf-8")
    console.print(f"[green]wrote {out}[/green]")


if __name__ == "__main__":
    app()
