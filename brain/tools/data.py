"""Data tools — analysis, SQL queries, charts, reports."""
from brain.tools.registry import tool


@tool(
    description="Load and analyze a data file (CSV, Excel, JSON, SQLite). Returns: shape, column types, missing values, descriptive stats, correlations, and a data preview. Optionally answers a specific question about the data.",
    parameters={
        "path":     {"type": "string", "description": "Path to the data file (CSV, .xlsx, .json, .sqlite, .tsv)"},
        "question": {"type": "string", "description": "Optional specific question to answer about the data"},
    }
)
def analyze_data(path: str, question: str = None) -> str:
    from control.analyst import analyze_data as _run
    return _run(path, question)


@tool(
    description="Run a SQL query against any data file (CSV, Excel, JSON). The file is loaded as a table called 'data' in an in-memory SQLite database.",
    parameters={
        "path": {"type": "string", "description": "Path to the data file"},
        "sql":  {"type": "string", "description": "SQL query to run (table name is always 'data')"},
    }
)
def query_data(path: str, sql: str) -> str:
    from control.analyst import query_data as _run
    return _run(path, sql)


@tool(
    description="Generate a chart from a data file and display it in the HUD. Supported types: line, bar, scatter, pie, histogram, heatmap, box, area, candlestick.",
    parameters={
        "data_path":  {"type": "string", "description": "Path to the data file (CSV, Excel, JSON)"},
        "chart_type": {"type": "string", "description": "Chart type: line | bar | scatter | pie | histogram | heatmap | box | area | candlestick"},
        "x":          {"type": "string", "description": "Column name for x-axis (auto-selected if omitted)"},
        "y":          {"type": "string", "description": "Column name for y-axis / values (auto-selected if omitted)"},
        "title":      {"type": "string", "description": "Chart title (auto-generated if omitted)"},
        "hue":        {"type": "string", "description": "Column to use for color grouping (optional)"},
        "bins":       {"type": "integer", "description": "Number of bins for histogram (default: 30)"},
        "top_n":      {"type": "integer", "description": "Limit bar/pie to top N entries (optional)"},
    }
)
def generate_chart(data_path: str, chart_type: str, x: str = None, y: str = None,
                   title: str = None, hue: str = None, bins: int = 30, top_n: int = None) -> str:
    from control.charts import generate_chart as _run
    result = _run(data_path=data_path, chart_type=chart_type, x=x, y=y,
                  title=title, hue=hue, bins=bins, top_n=top_n)
    if result.endswith(".png") and not result.startswith("Chart") and not result.startswith("Could"):
        return f"Chart saved to {result}\n[CHART: {result}]"
    return result


@tool(
    description="List all charts that have been saved to ~/Desktop/jarvis_charts/.",
    parameters={}
)
def list_charts() -> str:
    from control.charts import list_charts as _run
    return _run()


@tool(
    description="Generate a professional report (PDF, Excel, or HTML) with charts and data. Saves to ~/Desktop/jarvis_reports/.",
    parameters={
        "title":         {"type": "string", "description": "Report title"},
        "sections":      {"type": "array",  "description": "Report sections with 'heading', 'content', and optional 'chart' (PNG path)"},
        "output_format": {"type": "string", "description": "Output format: pdf | excel | html (default: pdf)"},
        "data_path":     {"type": "string", "description": "Optional data file to auto-include an analysis section"},
        "output_path":   {"type": "string", "description": "Custom output path (optional)"},
    }
)
def generate_report(title: str, sections: list = None, output_format: str = "pdf",
                    data_path: str = None, output_path: str = None) -> str:
    from control.reports import generate_report as _run
    result = _run(title=title, sections=sections or [], output_format=output_format,
                  output_path=output_path, data_path=data_path)
    return f"Report saved to {result}"
