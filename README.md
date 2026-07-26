# Symrise Data Engineering Challenge — Sergio Diaz

Work in progress. Full setup instructions, pipeline usage, design decisions,
data quality findings, and business question answers will be documented here
as the solution is completed. See `challengers/README.md` for the original
challenge brief.

3. feat: implement data extraction (src/extract.py) — carga de los 4 CSV a DataFrames con manejo básico de errores.
4. feat: implement data validation (src/validate.py) — chequeos de esquema/calidad usando quality_thresholds de pipeline_config.yaml (ratings fuera de rango, nulos, duplicados, fechas inválidas).
5. feat: implement data transformation (src/transform.py) — limpieza (normalizar categorías, tipos, fechas), enriquecimiento (unir ingredientes-costos).
6. feat: implement SQLite load layer (src/load.py) — esquema (dimensional: products, sales, feedback, ingredient_costs) vía SQLAlchemy y carga idempotente.
7. feat: add ETL pipeline orchestrator (src/pipeline.py) — extract → validate → transform → load end-to-end, logging a output/pipeline.log.
8. feat: add SQL business-question queries (sql/queries.sql) — las 5 preguntas de negocio.
9. feat: add exploratory analysis queries (sql/analysis.sql).
10. feat: add visualizations for business metrics — script/notebook usando seaborn/matplotlib, guardado en output/visualizations/.
11. test: add unit tests for extract/validate/transform (tests/).
12. docs: add data quality report (output/data_quality_report.md).
13. docs: add business question answers (output/business_answers.md).
14. docs: write project README (setup, cómo correr el pipeline, decisiones de diseño, supuestos, limitaciones) — reemplaza el placeholder actual.