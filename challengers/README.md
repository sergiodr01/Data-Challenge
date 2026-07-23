# Symrise Data Engineering Challenge

## Welcome!

Thank you for your interest in joining Symrise as a Junior Data Engineer! This challenge is designed to assess your ability to work with real-world data scenarios similar to those you'll encounter in our flavors and fragrances business.

## Background

Symrise operates globally in the flavors and fragrances industry, creating innovative products for food, beverages, cosmetics, and personal care applications. Our R&D teams develop thousands of formulations, which are then sold to clients worldwide.

## The Challenge

You've been provided with sample datasets from three different sources within our organization:

1. **Product Formulations** - Data about our fragrance and flavor products, including ingredients and categories
2. **Sales Transactions** - Historical sales data across different regions and clients
3. **Customer Feedback** - Quality ratings and feedback from our B2B customers

### Your Mission

Build a **data pipeline and analytics solution** that:

1. **Ingests and validates** data from all three sources
2. **Cleans and transforms** the data to handle quality issues
3. **Documents** your approach and decisions

## Datasets Provided

All datasets are located in the `data/` folder:

- `products.csv` - Product formulation master data
- `sales_transactions.csv` - Sales records
- `customer_feedback.csv` - Customer satisfaction data
- `ingredient_costs.csv` - Raw material cost information

**Note:** These datasets contain intentional data quality issues that you'll need to identify and address.

## Technical Requirements

### Must Have:
- ✅ Python-based solution (3.12+)
- ✅ Data validation and quality checks
- ✅ ETL pipeline that can be executed end-to-end
- ✅ SQL database (SQLite, PostgreSQL, or similar)
- ✅ Clear documentation (README with setup instructions)
- ✅ Basic error handling

### Nice to Have:
- ⭐ Unit tests for critical functions
- ⭐ Data quality report/logging
- ⭐ Visualization of key metrics
- ⭐ Configuration file for parameters

## Deliverables

Please submit:

1. **Source Code** - All scripts, SQL files, and configuration
2. **Documentation** - README with:
   - Setup instructions
   - How to run the pipeline
   - Design decisions and assumptions
   - Data quality issues found and how you handled them
3. **Database** - Final database file or schema + sample queries
4. **Analysis** - Answer to business questions (see below)

## Business Questions to Answer

Using your pipeline and data model, provide answers to:

1. **What are the top 5 best-selling product categories by revenue?**
2. **Which region has the highest average customer satisfaction score?**
3. **What is the relationship between product complexity (number of ingredients) and customer satisfaction?**
4. **Identify products with declining sales trends (compare last 2 quarters)**
5. **What is the profit margin for each product category?** (Revenue - Ingredient Costs)

If you think a question cannot be answered, you should explain the logic behind your thoughts.

## Submission Format

Please organize your submission as:

```
your-name-symrise-challenge/
├── README.md                 # Your documentation
├── requirements.txt          # Python dependencies
├── src/                      # Your source code
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   ├── or_a_single_notebook.ipynb
│   └── ...
├── sql/                      # SQL scripts
│   └── queries.sql
└── output/                   # Results, reports, visualizations
    ├── data_quality_report.md
    └── business_answers.md
```

## Evaluation Criteria

You will be evaluated on:

- **Code Quality** - Clean, readable, well-organized code
- **Data Engineering Skills** - ETL design, data modeling, SQL proficiency
- **Problem Solving** - How you handle data quality issues
- **Documentation** - Clear explanations of your approach
- **Completeness** - Meeting the requirements

## Timeline

You have **4-5 days** from receiving this challenge. Please submit your solution via:
- GitHub repository - share the link with us
- Or ZIP file via email

## Interview

You'll present your solution in a **30-minute session**:
(No need to make a powerpoint, it will most likely go through screen-sharing)
- 10 min: Walk through your solution
- 10 min: Technical deep-dive
- 10 min: Q&A and discussion

## Questions?

If you have any clarifying questions about the challenge, please reach out to louis-piotr.labadie.external@symrise.com

## Tips

- Start simple - get a basic pipeline working, then enhance it
- Document your assumptions
- Data quality matters - show us how you think about data issues
- We value working code over perfect code
- Have fun! This is meant to showcase your skills, not trick you

---

**Good luck! We're excited to see your solution! 🚀**

*Note: All data provided is synthetic and for assessment purposes only.*
