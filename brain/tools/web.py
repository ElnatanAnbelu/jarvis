"""Web tools — search, news, weather, prices, browser."""
from brain.tools.registry import tool


@tool(
    description="Search the web for information",
    parameters={
        "query": {"type": "string", "description": "Search query"},
    }
)
def web_search(query: str) -> str:
    from control.search import web_search as _search
    return _search(query)


@tool(
    description="Get the latest news relevant to the user's interests.",
    parameters={}
)
def get_news() -> str:
    from brain.news import get_news as _get
    return _get()


@tool(
    description="Get current weather for a city",
    parameters={
        "city": {"type": "string", "description": "City name, e.g. 'New York'"},
    }
)
def get_weather(city: str) -> str:
    try:
        import urllib.request, json
        city_enc = city.replace(" ", "+")
        url = f"https://wttr.in/{city_enc}?format=j1"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
        c = data["current_condition"][0]
        desc = c["weatherDesc"][0]["value"]
        temp_f = c["temp_F"]
        feels_f = c["FeelsLikeF"]
        humidity = c["humidity"]
        return f"{city}: {desc}, {temp_f}°F (feels {feels_f}°F), humidity {humidity}%"
    except Exception as e:
        return f"Could not get weather: {e}"


@tool(
    description="Get the current price of a cryptocurrency or stock ticker",
    parameters={
        "symbol": {"type": "string", "description": "Crypto name (bitcoin, ethereum, solana) or stock ticker (AAPL, TSLA, NVDA)"},
    }
)
def get_price(symbol: str) -> str:
    import urllib.request, json
    symbol = symbol.strip().lower()
    COIN_IDS = {
        "btc": "bitcoin", "bitcoin": "bitcoin",
        "eth": "ethereum", "ethereum": "ethereum",
        "sol": "solana", "solana": "solana",
        "bnb": "binancecoin", "xrp": "ripple",
        "doge": "dogecoin", "ada": "cardano",
    }
    coin_id = COIN_IDS.get(symbol)
    if coin_id:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
        with urllib.request.urlopen(url, timeout=8) as r:
            d = json.loads(r.read())
        price = d[coin_id]["usd"]
        change = d[coin_id].get("usd_24h_change", 0)
        return f"{coin_id.title()}: ${price:,.2f} ({change:+.2f}% 24h)"
    ticker = symbol.upper()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.loads(r.read())
    meta = d["chart"]["result"][0]["meta"]
    price = meta["regularMarketPrice"]
    prev = meta.get("chartPreviousClose", price)
    change_pct = ((price - prev) / prev * 100) if prev else 0
    return f"{ticker}: ${price:,.2f} ({change_pct:+.2f}%)"


@tool(
    description="Open a URL or local HTML file in Chrome. Use after scaffolding a frontend project or when the user asks to preview or open something in the browser.",
    parameters={
        "target": {"type": "string", "description": "URL (https://...) or absolute local file path to open in Chrome"},
    }
)
def open_in_browser(target: str) -> str:
    from control.browser import open_in_browser as _open
    return _open(target)
