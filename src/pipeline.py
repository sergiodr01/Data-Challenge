"""
ETL pipeline orchestrator: runs extract -> validate -> transform -> validate
-> load end-to-end, driven entirely by config/pipeline_config.yaml.

The second validate call is a quality gate: whatever issues survive
cleaning are the ones we deliberately chose not to (or can't) fix, and
they get logged and returned here instead of silently flowing into the
database untracked.
"""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from . import extract, load, transform, validate

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(path: str) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else PROJECT_ROOT / resolved


def _load_config(config_path: str) -> dict[str, Any]:
    config_file = _resolve(config_path)
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def configure_logging(config: dict[str, Any]) -> None:
    """Set up logging from config['logging'] (level + log_file) instead of
    hardcoding them, with both a console and a file handler."""
    log_config = config.get('logging', {})
    level = getattr(logging, str(log_config.get('level', 'INFO')).upper(), logging.INFO)
    log_file = log_config.get('log_file')

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_path = _resolve(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, mode='a', encoding='utf-8'))

    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
        handlers=handlers,
        force=True,
    )


def run_ingestion(
    config_path: str = "config/pipeline_config.yaml", schema_path: str = "config/schema.yaml"
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """
    Run the extract -> validate -> transform -> validate stages.

    Returns:
        (cleaned_data, post_transform_report): cleaned DataFrames ready to
        load, and the quality report for whatever issues remain after
        cleaning (empty lists per dataset if none remain).
    """
    config = _load_config(config_path)
    thresholds = config.get('quality_thresholds', {})
    schema = _load_config(schema_path)

    logger.info("Stage 1/5: extract")
    raw_data = extract.extract_all(config_path)

    logger.info("Stage 2/5: validate (pre-transform)")
    validate.validate_structure(raw_data, schema)
    pre_report = validate.validate_all(raw_data, schema, thresholds=thresholds)
    pre_total = sum(len(issues) for issues in pre_report.values())

    logger.info("Stage 3/5: transform")
    cleaned_data = transform.transform_all(raw_data, thresholds=thresholds, schema=schema)

    logger.info("Stage 4/5: validate (post-transform gate)")
    validate.validate_structure(cleaned_data, schema)
    post_report = validate.validate_all(cleaned_data, schema, thresholds=thresholds)
    post_total = sum(len(issues) for issues in post_report.values())

    logger.info(f"Quality gate: {pre_total} issue(s) before cleaning, {post_total} remain after cleaning")
    if post_total:
        logger.warning("Residual data quality issues after cleaning (see output/data_quality_report.md):")
        for dataset, issues in post_report.items():
            for issue in issues:
                logger.warning(f"  [{dataset}] {issue}")

    return cleaned_data, post_report


def run_pipeline(
    config_path: str = "config/pipeline_config.yaml", schema_path: str = "config/schema.yaml"
) -> dict[str, list[str]]:
    """
    Run the full pipeline end-to-end: extract -> validate -> transform ->
    validate -> load, persisting the cleaned data to the SQLite database
    declared in config['paths']['database'].

    Returns:
        The post-transform quality report (see run_ingestion()).
    """
    config = _load_config(config_path)
    schema = _load_config(schema_path)

    cleaned_data, post_report = run_ingestion(config_path, schema_path)

    logger.info("Stage 5/5: load")
    database_path = config['paths']['database']
    db_path = load.load_all(cleaned_data, schema, database_path=database_path)
    logger.info(f"Pipeline complete. Database written to {db_path}")

    return post_report


#: Exceptions that mean "your data or config is broken", not "there's a bug
#: in this code". For these, a short logged message is more useful at the
#: command line than a full Python traceback.
EXPECTED_FAILURES = (
    validate.SchemaValidationError,
    FileNotFoundError,
    KeyError,
    pd.errors.EmptyDataError,
    pd.errors.ParserError,
)


if __name__ == "__main__":
    _bootstrap_config = _load_config("config/pipeline_config.yaml")
    configure_logging(_bootstrap_config)
    try:
        run_pipeline()
    except EXPECTED_FAILURES as e:
        # extract.py and validate.py already log the specific cause with
        # full context (which dataset, which file, which column). This is
        # just the final, short "stop" message for the terminal - the
        # detail is above it, not hidden in a traceback.
        logger.error(f"Pipeline stopped: {e}")
        raise SystemExit(1) from e
