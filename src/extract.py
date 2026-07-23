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

        paths = config['paths']
        logger.info(f"Configuration loaded from {config_file}")

        # Extract all datasets
        data = {
            'products': pd.read_csv(_resolve(paths['products_csv']), encoding='utf-8'),
            'sales': pd.read_csv(_resolve(paths['sales_csv']), encoding='utf-8'),
            'feedback': pd.read_csv(_resolve(paths['feedback_csv']), encoding='utf-8'),
            'ingredients': pd.read_csv(_resolve(paths['ingredient_costs_csv']), encoding='utf-8')
        }

        logger.info(f"Extracted {len(data['products'])} products")
        logger.info(f"Extracted {len(data['sales'])} sales transactions")
        logger.info(f"Extracted {len(data['feedback'])} feedback records")
        logger.info(f"Extracted {len(data['ingredients'])} ingredients")

        return data

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error during extraction: {e}")
        raise
