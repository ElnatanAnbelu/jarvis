"""
Data analysis engine — load CSV, Excel, JSON, SQL dumps and return insights.
"""
import os
import json
import sqlite3
import tempfile
from pathlib import Path


def _expand(path: str) -> str:
    return str(Path(os.path.expanduser(path)).resolve())


def _load_dataframe(path: str):
    """Load a file into a pandas DataFrame. Returns (df, error_str)."""
    try:
        import pandas as pd
    except ImportError:
        return None, "pandas not installed"

    full = _expand(path)
    if not os.path.exists(full):
        return None, f"File not found: {full}"

    ext = Path(full).suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(full)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(full)
        elif ext == ".json":
            df = pd.read_json(full)
        elif ext in (".tsv", ".txt"):
            df = pd.read_csv(full, sep="\t")
        elif ext in (".sql", ".db", ".sqlite", ".sqlite3"):
            conn = sqlite3.connect(full)
            tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
            if tables.empty:
                conn.close()
                return None, "No tables found in database."
            first_table = tables["name"].iloc[0]
            df = pd.read_sql(f"SELECT * FROM {first_table} LIMIT 5000", conn)
            conn.close()
        else:
            # Try CSV as fallback
            df = pd.read_csv(full)
        return df, None
    except Exception as e:
        return None, f"Could not load file: {e}"


def analyze_data(path: str, question: str = None) -> str:
    """
    Load and analyze a data file. Runs full EDA or answers a specific question.
    Supports: CSV, Excel, JSON, TSV, SQLite
    """
    df, err = _load_dataframe(path)
    if err:
        return err

    import pandas as pd
    import numpy as np

    lines = []
    full = _expand(path)
    lines.append(f"FILE: {Path(full).name}")
    lines.append(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    lines.append("")

    # Column overview
    lines.append("COLUMNS:")
    for col in df.columns:
        dtype = str(df[col].dtype)
        nulls = df[col].isna().sum()
        null_str = f"  ({nulls:,} nulls)" if nulls > 0 else ""
        if pd.api.types.is_numeric_dtype(df[col]):
            lines.append(f"  {col} [{dtype}]{null_str}")
        else:
            uniq = df[col].nunique()
            lines.append(f"  {col} [{dtype}] — {uniq} unique values{null_str}")
    lines.append("")

    # Numeric summary
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if num_cols:
        lines.append("NUMERIC SUMMARY:")
        desc = df[num_cols].describe().round(2)
        lines.append(desc.to_string())
        lines.append("")

    # Missing values
    total_nulls = df.isna().sum().sum()
    if total_nulls > 0:
        lines.append("MISSING VALUES:")
        missing = df.isna().sum()
        for col, cnt in missing[missing > 0].items():
            pct = cnt / len(df) * 100
            lines.append(f"  {col}: {cnt:,} missing ({pct:.1f}%)")
        lines.append("")

    # Correlations (numeric only, if enough columns)
    if len(num_cols) >= 2:
        corr = df[num_cols].corr().round(3)
        # Find strong correlations (above 0.5, exclude self)
        strong = []
        for i, c1 in enumerate(corr.columns):
            for j, c2 in enumerate(corr.columns):
                if j <= i:
                    continue
                val = corr.loc[c1, c2]
                if abs(val) >= 0.5:
                    direction = "positive" if val > 0 else "negative"
                    strong.append(f"  {c1} ↔ {c2}: {val:.3f} ({direction})")
        if strong:
            lines.append("STRONG CORRELATIONS (|r| ≥ 0.5):")
            lines.extend(strong)
            lines.append("")

    # Sample rows
    lines.append("FIRST 5 ROWS:")
    lines.append(df.head(5).to_string(index=False))

    result = "\n".join(lines)

    # If a specific question was asked, answer it
    if question:
        lines.append("")
        lines.append(f"QUESTION: {question}")
        answer = _answer_question(df, question)
        lines.append(f"ANSWER: {answer}")
        result = "\n".join(lines)

    return result


def _answer_question(df, question: str) -> str:
    """Try to answer a data question with simple heuristics."""
    import pandas as pd
    import numpy as np

    q = question.lower()

    # Total / sum
    if any(w in q for w in ["total", "sum", "how much"]):
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if num_cols:
            sums = {c: df[c].sum() for c in num_cols}
            return ", ".join(f"{c}: {v:,.2f}" for c, v in sums.items())

    # Average / mean
    if any(w in q for w in ["average", "mean", "avg"]):
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if num_cols:
            means = {c: df[c].mean() for c in num_cols}
            return ", ".join(f"{c}: {v:,.2f}" for c, v in means.items())

    # Count / how many
    if any(w in q for w in ["how many", "count", "number of"]):
        return f"{len(df):,} rows"

    # Max / highest
    if any(w in q for w in ["max", "highest", "largest", "top", "best"]):
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if num_cols:
            maxes = {c: df[c].max() for c in num_cols}
            return ", ".join(f"{c}: {v:,.2f}" for c, v in maxes.items())

    # Min / lowest
    if any(w in q for w in ["min", "lowest", "smallest", "bottom", "worst"]):
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if num_cols:
            mins = {c: df[c].min() for c in num_cols}
            return ", ".join(f"{c}: {v:,.2f}" for c, v in mins.items())

    # Trend
    if any(w in q for w in ["trend", "over time", "growth"]):
        return "To analyze trends, specify a date column and a value column, then ask me to generate a line chart."

    return "I can run more specific analysis — tell me exactly what you want to know (totals, averages, trends, specific column, filter conditions, etc.)"


def query_data(path: str, sql: str) -> str:
    """
    Run a SQL query against a data file.
    Loads the file into an in-memory SQLite DB as table 'data', runs the query.
    """
    df, err = _load_dataframe(path)
    if err:
        return err

    try:
        conn = sqlite3.connect(":memory:")
        df.to_sql("data", conn, index=False, if_exists="replace")
        import pandas as pd
        result_df = pd.read_sql(sql, conn)
        conn.close()
        if result_df.empty:
            return "Query returned no results."
        return result_df.to_string(index=False)
    except Exception as e:
        return f"SQL error: {e}"
