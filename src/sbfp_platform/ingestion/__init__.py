"""Bronze ingestion: discovery, readers, alias mapping, drift capture, parquet writing.

The public surface is :func:`~sbfp_platform.ingestion.run.run_ingestion`, which the CLI
calls. Everything else exists so the pieces can be unit-tested on their own.
"""

from sbfp_platform.ingestion.run import IngestionResult, run_ingestion

__all__ = ["IngestionResult", "run_ingestion"]
