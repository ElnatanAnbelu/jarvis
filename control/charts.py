"""
Chart generation engine — produces styled PNG charts from data files.
Saves to ~/Desktop/jarvis_charts/. Returns file path JARVIS can reference.
"""
import os
import time
from pathlib import Path


CHARTS_DIR = os.path.expanduser("~/Desktop/jarvis_charts")
CHART_TYPES = ["line", "bar", "scatter", "pie", "histogram", "heatmap", "box", "candlestick", "area"]


def _ensure_dir():
    os.makedirs(CHARTS_DIR, exist_ok=True)


def _load_df(path: str):
    from control.analyst import _load_dataframe
    df, err = _load_dataframe(path)
    return df, err


def _apply_hud_style():
    """Apply Iron Man / dark HUD matplotlib style."""
    import matplotlib.pyplot as plt
    import matplotlib as mpl

    plt.rcParams.update({
        "figure.facecolor":  "#080f14",
        "axes.facecolor":    "#0a1520",
        "axes.edgecolor":    "#00FFFF44",
        "axes.labelcolor":   "#00FFFF",
        "axes.titlecolor":   "#00FFFF",
        "axes.grid":         True,
        "grid.color":        "#00FFFF18",
        "grid.linewidth":    0.5,
        "xtick.color":       "#00FFFF88",
        "ytick.color":       "#00FFFF88",
        "text.color":        "#e0e0e0",
        "figure.dpi":        150,
        "font.family":       "monospace",
        "font.size":         9,
        "axes.titlesize":    11,
        "axes.labelsize":    9,
        "legend.facecolor":  "#0a1520",
        "legend.edgecolor":  "#00FFFF44",
        "legend.labelcolor": "#e0e0e0",
    })

    # HUD accent colors for data series
    mpl.rcParams["axes.prop_cycle"] = mpl.cycler(color=[
        "#00FFFF", "#00FF9F", "#FF4C4C", "#FFD700", "#7B68EE", "#FF6B9D", "#00BFFF"
    ])


def generate_chart(
    data_path: str,
    chart_type: str,
    x: str = None,
    y: str = None,
    title: str = None,
    hue: str = None,
    bins: int = 30,
    top_n: int = None,
) -> str:
    """
    Generate a chart from a data file.
    Returns the saved PNG file path (or error string).

    chart_type: line | bar | scatter | pie | histogram | heatmap | box | area
    x, y: column names
    title: chart title (auto-generated if omitted)
    hue: grouping column for color separation
    bins: bins for histogram
    top_n: limit bar/pie to top N values
    """
    _ensure_dir()
    df, err = _load_df(data_path)
    if err:
        return err

    import matplotlib.pyplot as plt
    import numpy as np

    _apply_hud_style()

    ct = chart_type.lower().strip()
    if ct not in CHART_TYPES:
        return f"Unknown chart type '{chart_type}'. Supported: {', '.join(CHART_TYPES)}"

    # Auto-select columns if not specified
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

    if not x and ct not in ("histogram", "heatmap", "box"):
        x = cat_cols[0] if cat_cols else (num_cols[0] if num_cols else None)
    if not y and num_cols:
        y = num_cols[0] if (not x or x not in num_cols) else (num_cols[1] if len(num_cols) > 1 else num_cols[0])

    fig, ax = plt.subplots(figsize=(10, 5.5))
    label = title or f"{ct.upper()} — {Path(data_path).stem}"
    ax.set_title(label, pad=12, fontweight="bold")

    try:
        if ct == "line":
            if x and y:
                if hue and hue in df.columns:
                    for grp, sub in df.groupby(hue):
                        ax.plot(sub[x], sub[y], label=str(grp), linewidth=1.6)
                    ax.legend()
                else:
                    ax.plot(df[x], df[y], linewidth=1.8)
                ax.set_xlabel(x); ax.set_ylabel(y)
            else:
                for col in num_cols[:4]:
                    ax.plot(df[col], label=col, linewidth=1.6)
                ax.legend()

        elif ct == "area":
            if x and y:
                ax.fill_between(range(len(df)), df[y], alpha=0.3)
                ax.plot(range(len(df)), df[y], linewidth=1.8)
                ax.set_xlabel(x); ax.set_ylabel(y)
            else:
                col = num_cols[0] if num_cols else None
                if col:
                    ax.fill_between(range(len(df)), df[col], alpha=0.3)
                    ax.plot(range(len(df)), df[col], linewidth=1.8)
                    ax.set_ylabel(col)

        elif ct == "bar":
            if x and y:
                data = df.groupby(x)[y].sum().reset_index()
                if top_n:
                    data = data.nlargest(top_n, y)
                ax.bar(data[x].astype(str), data[y], color="#00FFFF", alpha=0.8, edgecolor="#00FFFF44")
                ax.set_xlabel(x); ax.set_ylabel(y)
                if len(data) > 8:
                    ax.tick_params(axis="x", rotation=45)
            elif num_cols:
                col = num_cols[0]
                counts = df[col].value_counts()
                if top_n:
                    counts = counts.head(top_n)
                ax.bar(counts.index.astype(str), counts.values, color="#00FFFF", alpha=0.8)
                ax.set_ylabel("Count")

        elif ct == "scatter":
            if x and y:
                colors = None
                if hue and hue in df.columns:
                    cats = df[hue].astype("category")
                    colors = cats.cat.codes
                ax.scatter(df[x], df[y], c=colors, alpha=0.6, s=20, cmap="cool")
                ax.set_xlabel(x); ax.set_ylabel(y)
            elif len(num_cols) >= 2:
                ax.scatter(df[num_cols[0]], df[num_cols[1]], alpha=0.6, s=20, color="#00FFFF")
                ax.set_xlabel(num_cols[0]); ax.set_ylabel(num_cols[1])

        elif ct == "histogram":
            col = y or x or (num_cols[0] if num_cols else None)
            if col and col in df.columns:
                ax.hist(df[col].dropna(), bins=bins, color="#00FFFF", alpha=0.75, edgecolor="#00FFFF44")
                ax.set_xlabel(col); ax.set_ylabel("Frequency")
            else:
                return "Specify a column name for histogram."

        elif ct == "pie":
            col = x or (cat_cols[0] if cat_cols else num_cols[0] if num_cols else None)
            val_col = y or (num_cols[0] if num_cols else None)
            if col:
                if val_col and val_col in df.columns:
                    data = df.groupby(col)[val_col].sum()
                else:
                    data = df[col].value_counts()
                if top_n:
                    data = data.nlargest(top_n)
                colors = ["#00FFFF", "#00FF9F", "#FF4C4C", "#FFD700", "#7B68EE", "#FF6B9D", "#00BFFF"]
                wedges, texts, autotexts = ax.pie(
                    data.values, labels=data.index.astype(str),
                    autopct="%1.1f%%", colors=colors[:len(data)],
                    textprops={"color": "#e0e0e0", "fontsize": 8}
                )
                for at in autotexts:
                    at.set_color("#080f14")
            else:
                return "Could not determine data column for pie chart."

        elif ct == "heatmap":
            if len(num_cols) < 2:
                return "Need at least 2 numeric columns for a heatmap."
            corr = df[num_cols].corr()
            import matplotlib.colors as mcolors
            cmap = plt.cm.get_cmap("cool")
            im = ax.imshow(corr, cmap=cmap, aspect="auto", vmin=-1, vmax=1)
            ax.set_xticks(range(len(num_cols)))
            ax.set_yticks(range(len(num_cols)))
            ax.set_xticklabels(num_cols, rotation=45, ha="right", fontsize=7)
            ax.set_yticklabels(num_cols, fontsize=7)
            for i in range(len(num_cols)):
                for j in range(len(num_cols)):
                    ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center",
                            color="white", fontsize=6)
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        elif ct == "box":
            cols = [y] if y and y in df.columns else num_cols[:6]
            df[cols].boxplot(ax=ax, patch_artist=True,
                             boxprops=dict(facecolor="#00FFFF22", color="#00FFFF"),
                             medianprops=dict(color="#00FF9F", linewidth=2),
                             whiskerprops=dict(color="#00FFFF88"),
                             capprops=dict(color="#00FFFF88"),
                             flierprops=dict(markerfacecolor="#FF4C4C", markersize=3))

        elif ct == "candlestick":
            # Expect OHLC columns: open, high, low, close (case-insensitive)
            col_map = {c.lower(): c for c in df.columns}
            req = ["open", "high", "low", "close"]
            missing_cols = [r for r in req if r not in col_map]
            if missing_cols:
                return f"Candlestick needs columns: open, high, low, close. Missing: {missing_cols}"
            o = df[col_map["open"]].values
            h = df[col_map["high"]].values
            l = df[col_map["low"]].values
            c = df[col_map["close"]].values
            for i in range(len(df)):
                color = "#00FF9F" if c[i] >= o[i] else "#FF4C4C"
                ax.plot([i, i], [l[i], h[i]], color=color, linewidth=0.8)
                ax.add_patch(plt.Rectangle((i - 0.3, min(o[i], c[i])), 0.6, abs(c[i] - o[i]),
                                           color=color, alpha=0.8))
            ax.set_ylabel("Price")

    except Exception as e:
        plt.close(fig)
        return f"Chart generation error: {e}"

    plt.tight_layout()

    # Save
    ts = int(time.time())
    filename = f"{ct}_{ts}.png"
    save_path = os.path.join(CHARTS_DIR, filename)
    try:
        fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return save_path
    except Exception as e:
        plt.close(fig)
        return f"Could not save chart: {e}"


def list_charts() -> str:
    """List all saved charts in the charts directory."""
    _ensure_dir()
    files = sorted(Path(CHARTS_DIR).glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return f"No charts saved yet. Charts are saved to {CHARTS_DIR}"
    lines = [f"Charts in {CHARTS_DIR}:"]
    for f in files[:20]:
        size = f.stat().st_size // 1024
        lines.append(f"  {f.name}  ({size}KB)")
    return "\n".join(lines)
