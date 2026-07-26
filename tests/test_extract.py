from pathlib import Path

import pandas as pd
import pytest
import yaml

from src import extract


def _write_config(tmp_path: Path, paths: dict[str, str]) -> Path:
    config = {'paths': paths}
    config_path = tmp_path / 'pipeline_config.yaml'
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f)
    return config_path


def _write_csvs(tmp_path: Path) -> dict[str, str]:
    products = pd.DataFrame({'product_id': ['P001'], 'product_name': ['Citrus Burst']})
    sales = pd.DataFrame({'transaction_id': ['T001'], 'product_id': ['P001']})
    feedback = pd.DataFrame({'feedback_id': ['F001'], 'product_id': ['P001']})
    ingredients = pd.DataFrame({'ingredient_id': ['I001'], 'ingredient_name': ['Lemon Oil']})

    products.to_csv(tmp_path / 'products.csv', index=False)
    sales.to_csv(tmp_path / 'sales.csv', index=False)
    feedback.to_csv(tmp_path / 'feedback.csv', index=False)
    ingredients.to_csv(tmp_path / 'ingredients.csv', index=False)

    return {
        'products_csv': str(tmp_path / 'products.csv'),
        'sales_csv': str(tmp_path / 'sales.csv'),
        'feedback_csv': str(tmp_path / 'feedback.csv'),
        'ingredient_costs_csv': str(tmp_path / 'ingredients.csv'),
    }


class TestExtractAll:
    def test_loads_all_four_datasets(self, tmp_path):
        paths = _write_csvs(tmp_path)
        config_path = _write_config(tmp_path, paths)

        data = extract.extract_all(str(config_path))

        assert set(data) == {'products', 'sales', 'feedback', 'ingredients'}
        assert len(data['products']) == 1
        assert data['products'].iloc[0]['product_id'] == 'P001'
        assert isinstance(data['sales'], pd.DataFrame)

    def test_missing_config_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract.extract_all(str(tmp_path / 'does_not_exist.yaml'))

    def test_missing_csv_raises_file_not_found(self, tmp_path):
        paths = _write_csvs(tmp_path)
        paths['products_csv'] = str(tmp_path / 'missing.csv')
        config_path = _write_config(tmp_path, paths)

        with pytest.raises(FileNotFoundError):
            extract.extract_all(str(config_path))

    def test_missing_csv_error_names_the_dataset(self, tmp_path):
        paths = _write_csvs(tmp_path)
        paths['feedback_csv'] = str(tmp_path / 'missing.csv')
        config_path = _write_config(tmp_path, paths)

        with pytest.raises(FileNotFoundError, match="feedback"):
            extract.extract_all(str(config_path))

    def test_missing_paths_section_raises_key_error(self, tmp_path):
        config_path = tmp_path / 'pipeline_config.yaml'
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({'logging': {'level': 'INFO'}}, f)

        with pytest.raises(KeyError):
            extract.extract_all(str(config_path))
