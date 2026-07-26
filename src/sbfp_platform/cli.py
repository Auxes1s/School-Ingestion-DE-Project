"""Command line interface.

Frozen contract: command names, options, and the module-level function each command
delegates to are fixed. Slices implement the delegated functions; they do not edit this
file. Imports are deliberately performed inside command bodies so the CLI stays usable
while later slices are still unimplemented.
"""

from __future__ import annotations

import importlib
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from sbfp_platform.config import VALID_PROFILES, load_config

app = typer.Typer(
    name="sbfp-platform",
    help="Synthetic public-sector data platform for school feeding M&E.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

ProfileOpt = Annotated[
    str | None,
    typer.Option("--profile", "-p", help=f"Scale profile: {', '.join(VALID_PROFILES)}."),
]
SeedOpt = Annotated[int | None, typer.Option("--seed", help="Master random seed.")]


def _delegate(module_path: str, func_name: str, /, **kwargs):
    """Call ``func_name`` in ``module_path``, with a clear message if the slice is absent."""
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("sbfp_platform"):
            console.print(
                f"[yellow]Not yet implemented:[/yellow] {module_path} is missing. "
                "This command becomes available when its build slice lands."
            )
            raise typer.Exit(code=2) from exc
        raise
    return getattr(module, func_name)(**kwargs)


@app.command()
def doctor(profile: ProfileOpt = None) -> None:
    """Verify configuration, paths, and optional dependencies."""
    cfg = load_config(profile=profile)

    table = Table(title="sbfp-platform doctor", show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Result")

    table.add_row("profile", cfg.profile)
    table.add_row("seed", str(cfg.seed))
    table.add_row("repo root", str(cfg.paths.root))
    scale = cfg.scale
    table.add_row("scale", f"{scale['schools']} schools / {scale['children']:,} children")
    table.add_row("dqa rules", str(len(cfg.dqa_rules)))
    table.add_row("raw dirs", "present" if cfg.paths.raw_data_dir.exists() else "not generated")
    table.add_row("lakehouse", "present" if cfg.paths.lakehouse_dir.exists() else "not built")

    for dep in ("duckdb", "pandera", "splink", "dbt", "dagster", "streamlit"):
        try:
            importlib.import_module(dep)
            table.add_row(f"dep: {dep}", "[green]ok[/green]")
        except ImportError:
            table.add_row(f"dep: {dep}", "[red]missing[/red]")

    console.print(table)

    # Contract check: every detectable defect type must map to exactly one rule.
    unmapped = [
        d
        for d, detectable in cfg.detectable.items()
        if detectable and cfg.rule_for_defect(d) is None
    ]
    if unmapped:
        console.print(
            f"[red]Contract violation:[/red] detectable defect types with no DQA rule: "
            f"{', '.join(sorted(unmapped))}"
        )
        raise typer.Exit(code=1)
    console.print("[green]Config contracts hold.[/green]")


@app.command("generate-demo-data")
def generate_demo_data(profile: ProfileOpt = None, seed: SeedOpt = None) -> None:
    """Generate synthetic raw source files and the ground-truth answer key."""
    _delegate(
        "sbfp_platform.synthetic.generate",
        "generate_all",
        config=load_config(profile=profile, seed=seed),
    )


@app.command()
def ingest(
    profile: ProfileOpt = None,
    force: Annotated[
        bool, typer.Option("--force", help="Re-ingest files whose hash is unchanged.")
    ] = False,
) -> None:
    """Ingest raw source files into the bronze layer."""
    _delegate(
        "sbfp_platform.ingestion.run",
        "run_ingestion",
        config=load_config(profile=profile),
        force=force,
    )


@app.command("run-dqa")
def run_dqa(profile: ProfileOpt = None) -> None:
    """Run data quality checks and build the issue registry."""
    _delegate(
        "sbfp_platform.validation.run",
        "run_dqa",
        config=load_config(profile=profile),
    )


@app.command("run-linkage")
def run_linkage(profile: ProfileOpt = None) -> None:
    """Link baseline and endline records, deterministically then probabilistically."""
    _delegate(
        "sbfp_platform.linkage.run",
        "run_linkage",
        config=load_config(profile=profile),
    )


@app.command("build-silver")
def build_silver(profile: ProfileOpt = None) -> None:
    """Build silver models via dbt. Runs before linkage."""
    _delegate(
        "sbfp_platform.transforms.run",
        "build_silver",
        config=load_config(profile=profile),
    )


@app.command("build-gold")
def build_gold(profile: ProfileOpt = None) -> None:
    """Build gold models via dbt. Runs after linkage, which gold consumes."""
    _delegate(
        "sbfp_platform.transforms.run",
        "build_gold",
        config=load_config(profile=profile),
    )


@app.command()
def score(profile: ProfileOpt = None) -> None:
    """Score the pipeline against ground truth: DQA and linkage scorecards."""
    _delegate(
        "sbfp_platform.evaluation.run",
        "build_scorecards",
        config=load_config(profile=profile),
    )


@app.command()
def export(profile: ProfileOpt = None) -> None:
    """Write public export files from gold."""
    _delegate(
        "sbfp_platform.transforms.run",
        "build_exports",
        config=load_config(profile=profile),
    )


@app.command("full-refresh")
def full_refresh(profile: ProfileOpt = None, seed: SeedOpt = None) -> None:
    """Run the whole pipeline: generate, ingest, DQA, marts, linkage, score, export."""
    cfg = load_config(profile=profile, seed=seed)
    console.rule(f"[bold]full refresh — profile={cfg.profile} seed={cfg.seed}")
    # Order matters: linkage sits between the two dbt stages because gold consumes it
    # and it cannot be expressed in SQL (spec §4).
    for step, (module, func, kwargs) in {
        "generate": ("sbfp_platform.synthetic.generate", "generate_all", {}),
        "ingest": ("sbfp_platform.ingestion.run", "run_ingestion", {"force": False}),
        "silver": ("sbfp_platform.transforms.run", "build_silver", {}),
        "dqa": ("sbfp_platform.validation.run", "run_dqa", {}),
        "linkage": ("sbfp_platform.linkage.run", "run_linkage", {}),
        "gold": ("sbfp_platform.transforms.run", "build_gold", {}),
        "score": ("sbfp_platform.evaluation.run", "build_scorecards", {}),
        "export": ("sbfp_platform.transforms.run", "build_exports", {}),
    }.items():
        console.rule(f"[dim]{step}")
        _delegate(module, func, config=cfg, **kwargs)


if __name__ == "__main__":
    app()
