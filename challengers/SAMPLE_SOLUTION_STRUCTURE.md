# Sample Solution Structure

This document provides guidance on what a good submission structure might look like. Share this with candidates if they request clarification on expected deliverable format.

This is only an example,
there is no issue if you don't do it exactly like this

---

## example Project Structure

```
candidate-name-symrise-challenge/
│
├── README.md                          # Main documentation
├── requirements.txt                   # Python dependencies
├── .gitignore                        # Git ignore file
│
├── data/                             # Original data (read-only)
│   ├── products.csv
│   ├── sales_transactions.csv
│   ├── customer_feedback.csv
│   └── ingredient_costs.csv
│
├── src/                              # Source code
│   ├── extract.py                    # Data extraction logic
│   ├── transform.py                  # Data transformation/cleaning
│   ├── load.py                       # Database loading logic
│   └── validate.py                   # Data validation functions
│
├── sql/                              # SQL scripts
│   ├── queries.sql                   # Business question queries
│   └── analysis.sql                  # Additional analytical queries
│
│
├── notebooks/                        # (Optional) Jupyter notebooks
│   └── exploratory_analysis.ipynb
│
├── output/                           # Generated outputs
│   ├── data_quality_report.md        # Data quality findings
│   ├── business_answers.md           # Answers to business questions
│   ├── cleaned_data/                 # (Optional) Cleaned CSV files
│   └── visualizations/               # (Optional) Charts/graphs
│
├── config/                           # (Optional) Configuration files
│   └── pipeline_config.yaml
│
└── symrise_data.db                   # SQLite database (generated)
```

---

## Essential Files Description

### 1. README.md
**Must include:**
- Project overview
- Prerequisites (Python version, dependencies)
- Setup instructions
- How to run the pipeline
- Database schema overview
- Key design decisions
- Assumptions made
- Known limitations

**Example structure:**
```markdown
# Symrise Data Engineering Challenge - [Your Name]

## Overview
Brief description of the solution...

## Prerequisites
- Python 3.8+
- SQLite3

## Setup
1. Clone this repository
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
4. Install dependencies: `pip install -r requirements.txt`


## Design Decisions
- Chose SQLite for simplicity and portability
- Implemented star schema for dimensional modeling
- ...

**Good luck!** 🚀
