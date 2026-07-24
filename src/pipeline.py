"""
ETL pipeline orchestrator: runs extract -> validate -> transform -> validate.

The second validate call is a quality gate: whatever issues survive
cleaning are the ones we deliberately chose not to (or can't) fix, and
they get logged and returned here instead of silently flowing into the
database untracked. load.py (persisting cleaned_data to SQLite) plugs in
after this stage.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from . import extract, transform, validate

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_config(config_path: str) -> dict[str, Any]:
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = PROJECT_ROOT / config_file
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_ingestion(config_path: str = "config/pipeline_config.yaml") -> tuple[dict[str, Any], dict[str, list[str]]]:
    """
    Run the extract -> validate -> transform -> validate stages.

    Returns:
        (cleaned_data, post_transform_report): cleaned DataFrames ready to
        load, and the quality report for whatever issues remain after
        cleaning (empty lists per dataset if none remain).
    """
    config = _load_config(config_path)
    thresholds = config.get('quality_thresholds', {})

    logger.info("Stage 1/4: extract")
    raw_data = extract.extract_all(config_path)

    logger.info("Stage 2/4: validate (pre-transform)")
    pre_report = validate.validate_all(raw_data, thresholds=thresholds)
    pre_total = sum(len(issues) for issues in pre_report.values())

    logger.info("Stage 3/4: transform")
    cleaned_data = transform.transform_all(raw_data, thresholds=thresholds)

    logger.info("Stage 4/4: validate (post-transform gate)")
    post_report = validate.validate_all(cleaned_data, thresholds=thresholds)
    post_total = sum(len(issues) for issues in post_report.values())

    logger.info(f"Quality gate: {pre_total} issue(s) before cleaning, {post_total} remain after cleaning")
    if post_total:
        logger.warning("Residual data quality issues after cleaning (see output/data_quality_report.md):")
        for dataset, issues in post_report.items():
            for issue in issues:
                logger.warning(f"  [{dataset}] {issue}")

    return cleaned_data, post_report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    run_ingestion()
