"""Command line: fdash ingest | rebuild | status | serve."""

from __future__ import annotations

import logging

import typer

from fdash import settings
from fdash.ingest import runner
from fdash.ingest.registry import CONNECTORS, load_all
from fdash.store import db

load_all()
app = typer.Typer(help="Forecast dashboard", no_args_is_help=True)


def _run(sources: list[str], offline: bool) -> None:
    con = db.connect()
    runner.sync_catalog(con)
    failed = []
    for source_id in sources:
        result = runner.ingest_source(con, source_id, offline=offline)
        status = "ошибка" if result.error else "ok"
        typer.echo(
            f"{source_id:16} {status:7} выпусков +{result.releases_added:<4} строк +{result.rows_added}"
        )
        if result.error:
            typer.echo(f"  {result.error}", err=True)
            failed.append(source_id)
    con.close()
    if failed:
        raise typer.Exit(code=1)


@app.command()
def ingest(
    sources: list[str] = typer.Argument(None, help="source_id; без аргументов нужен --all"),
    all_sources: bool = typer.Option(False, "--all", help="Все источники"),
    offline: bool = typer.Option(False, help="Не обращаться к сети, только data/raw/"),
    verbose: bool = typer.Option(False, "-v"),
) -> None:
    """Скачать новые выпуски и загрузить их в базу."""
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)
    selected = sorted(CONNECTORS) if all_sources else (sources or [])
    if not selected:
        raise typer.BadParameter("Укажите источники или --all")
    _run(selected, offline)


@app.command()
def rebuild() -> None:
    """Пересобрать базу из data/raw/ без обращения к сети."""
    if settings.DB_PATH.exists():
        settings.DB_PATH.unlink()
    _run(sorted(CONNECTORS), offline=True)


@app.command()
def status() -> None:
    """Состояние данных по источникам."""
    if not settings.DB_PATH.exists():
        typer.echo("База ещё не создана: запустите fdash ingest --all")
        raise typer.Exit(code=1)
    con = db.connect(read_only=True)
    rows = con.execute(
        """
        SELECT s.source_id, count(r.release_id), max(r.vintage_date),
               (SELECT status FROM ingestion_log l WHERE l.source_id = s.source_id
                ORDER BY started_at DESC LIMIT 1)
        FROM sources s LEFT JOIN releases r USING (source_id)
        GROUP BY s.source_id ORDER BY s.source_id
        """
    ).fetchall()
    typer.echo(f"{'источник':16} {'выпусков':>8}  {'последний':10}  загрузка")
    for source_id, count, last, last_status in rows:
        typer.echo(f"{source_id:16} {count:>8}  {str(last or '—'):10}  {last_status or '—'}")


@app.command()
def serve(port: int = 8100, host: str = "127.0.0.1") -> None:
    """Запустить API и интерфейс."""
    import uvicorn

    typer.echo(f"Дашборд: http://{host}:{port}")
    uvicorn.run("fdash.api.app:app", host=host, port=port)


if __name__ == "__main__":
    app()
