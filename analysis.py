"""HR attrition analysis: data preparation, SQL queries (SQLite) and chi-square tests.

Run:  python analysis.py     (then python build_excel.py for the Excel workbook)
"""
import sqlite3
from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "hr_attrition_raw.csv"
CLEAN = ROOT / "data" / "hr_attrition_tableau.csv"
OUT = ROOT / "outputs"

QUERIES = {
    "attrition_by_department": """
        SELECT Department, COUNT(*) AS employees, SUM(attrition_flag) AS left_company,
               ROUND(100.0 * AVG(attrition_flag), 1) AS attrition_rate_pct
        FROM employees GROUP BY Department ORDER BY attrition_rate_pct DESC""",
    "job_role_vs_company_average": """
        WITH role_rate AS (
            SELECT JobRole, COUNT(*) AS employees, 100.0 * AVG(attrition_flag) AS rate
            FROM employees GROUP BY JobRole)
        SELECT JobRole, employees, ROUND(rate, 1) AS attrition_rate_pct,
               ROUND(rate - (SELECT 100.0 * AVG(attrition_flag) FROM employees), 1) AS gap_vs_company_pts,
               RANK() OVER (ORDER BY rate DESC) AS risk_rank
        FROM role_rate ORDER BY risk_rank""",
    "overtime_and_income": """
        SELECT OverTime,
               CASE WHEN MonthlyIncome < 3000 THEN '1. Under 3K' WHEN MonthlyIncome < 6000 THEN '2. 3K-6K'
                    WHEN MonthlyIncome < 10000 THEN '3. 6K-10K' ELSE '4. Above 10K' END AS income_band,
               COUNT(*) AS employees, ROUND(100.0 * AVG(attrition_flag), 1) AS attrition_rate_pct
        FROM employees GROUP BY OverTime, income_band ORDER BY OverTime, income_band""",
    "income_left_vs_stayed": """
        SELECT Attrition, COUNT(*) AS employees, ROUND(AVG(MonthlyIncome), 0) AS avg_monthly_income,
               ROUND(AVG(YearsAtCompany), 1) AS avg_years_at_company, ROUND(AVG(Age), 1) AS avg_age
        FROM employees GROUP BY Attrition""",
}


def prepare(raw):
    """Clean, band and rename columns for Tableau and Excel."""
    return pd.DataFrame({
        "Age Group": pd.cut(raw.Age, [17, 25, 35, 45, 60], labels=["18-25", "26-35", "36-45", "46-60"]),
        "Attrition": raw.Attrition.map({"Yes": "Left", "No": "Stayed"}),
        "Department": raw.Department,
        "Gender": raw.Gender,
        "Income Band": pd.cut(raw.MonthlyIncome, [0, 3000, 6000, 10000, 99999],
                              labels=["1. Under 3K", "2. 3K-6K", "3. 6K-10K", "4. Above 10K"]),
        "Job Role": raw.JobRole,
        "Overtime": raw.OverTime.map({"Yes": "Overtime", "No": "No Overtime"}),
        "Tenure Band": pd.cut(raw.YearsAtCompany, [-1, 2, 5, 10, 50],
                              labels=["1. 0-2 yrs", "2. 3-5 yrs", "3. 6-10 yrs", "4. 10+ yrs"]),
        "Attrition Flag": (raw.Attrition == "Yes").astype(int),
        "Monthly Income": raw.MonthlyIncome,
        "Years At Company": raw.YearsAtCompany,
    })


def chi_square(df, column):
    table = pd.crosstab(df[column], df["Attrition"])
    chi2, p, dof, _ = stats.chi2_contingency(table)
    return f"{column:14s} chi2={chi2:7.1f}  dof={dof}  p={p:.3g}"


def main():
    OUT.mkdir(exist_ok=True)
    raw = pd.read_csv(RAW)
    clean = prepare(raw)
    clean.to_csv(CLEAN, index=False)

    lines = ["HR ATTRITION - SUMMARY", "=" * 60,
             f"Employees: {len(raw):,}   Left: {clean['Attrition Flag'].sum()}   "
             f"Attrition rate: {100 * clean['Attrition Flag'].mean():.1f}%", ""]
    with sqlite3.connect(":memory:") as con:
        raw.assign(attrition_flag=(raw.Attrition == "Yes").astype(int)).to_sql("employees", con, index=False)
        for name, query in QUERIES.items():
            result = pd.read_sql_query(query, con)
            result.to_csv(OUT / f"{name}.csv", index=False)
            lines += [f"SQL: {name}", result.to_string(index=False), ""]

    lines += ["Chi-square tests of independence (is attrition related to ...?)"]
    lines += [chi_square(clean, col) for col in ["Overtime", "Department", "Age Group", "Income Band", "Tenure Band", "Gender"]]
    text = "\n".join(lines)
    (OUT / "summary.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
