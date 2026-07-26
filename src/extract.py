"""
Data extraction module: load raw CSVs into DataFrames.
Loads: products, sales_transactions, customer_feedback, ingredient_costs.
"""

import logging
from pathlib import Path

import pandas as pd
import yaml

# Anchor relative paths to the project root regardless of the caller's cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(path: str) -> Path:
    """Resolve a path from the config relative to the project root."""
    resolved = Path(path)
    return resolved if resolved.is_absolute() else PROJECT_ROOT / resolved



def extract_all(config_path: str = "config/pipeline_config.yaml") -> dict:
    """
    Extract all data from CSV files configured in pipeline_config.yaml.

    Args:
        config_path: Path to the pipeline configuration file, relative to
            the project root or absolute.

    Returns:
        Dictionary with keys: 'products', 'sales', 'feedback', 'ingredients'
        Each value is a pandas DataFrame.

    Raises:
        FileNotFoundError: If config file or CSV files are not found.
        Exception: For other data loading errors.
    """
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config_file = _resolve(config_path)
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        try:
            paths = config['paths']
        except KeyError as e:
            raise KeyError("Missing paths section in configuration") from e

        logger.info(f"Configuration loaded from {config_file}")

        # Extract all datasets, one at a time so a failure names its dataset
        # and the config key/path that caused it.
        dataset_keys = {
            'products': 'products_csv',
            'sales': 'sales_csv',
            'feedback': 'feedback_csv',
            'ingredients': 'ingredient_costs_csv',
        }

        data = {}
        for dataset_name, config_key in dataset_keys.items():
            try:
                csv_path = paths[config_key]
            except KeyError as e:
                raise KeyError(
                    f"Missing '{config_key}' under 'paths' in configuration "
                    f"(needed to load the '{dataset_name}' dataset)"
                ) from e

            resolved_path = _resolve(csv_path)
            try:
                data[dataset_name] = pd.read_csv(resolved_path, encoding='utf-8')
            except FileNotFoundError as e:
                raise FileNotFoundError(
                    f"Could not load '{dataset_name}' dataset: file not found at "
                    f"'{resolved_path}' (from config key '{config_key}')"
                ) from e
            except pd.errors.EmptyDataError as e:
                raise pd.errors.EmptyDataError(
                    f"Could not load '{dataset_name}' dataset: '{resolved_path}' has no "
                    f"content at all, not even a header row (from config key '{config_key}')"
                ) from e
            except pd.errors.ParserError as e:
                raise pd.errors.ParserError(
                    f"Could not load '{dataset_name}' dataset: '{resolved_path}' is not "
                    f"valid CSV (from config key '{config_key}'): {e}"
                ) from e

            logger.info(f"Extracted {len(data[dataset_name])} {dataset_name} rows")

        return data

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error during extraction: {e}")
        raise
