import os
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables (.env)
load_dotenv()

# Flexibly resolve Discord Webhook URL from .env
DISCORD_WEBHOOK_URL = (
        os.getenv('DISCORD_WEBHOOK_URL') or
        os.getenv('DISCORD_URL') or
        os.getenv('WEBHOOK_URL')
)


def get_dynamic_sp500_top10():
    """Dynamically scrapes the top 10 S&P 500 components by weight."""
    try:
        url = 'https://www.slickcharts.com/sp500'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)

        tables = pd.read_html(response.text)
        df = tables[0]

        symbols = df['Symbol'].head(10).str.replace('.', '-', regex=False).tolist()
        companies = df['Company'].head(10).tolist()

        return dict(zip(symbols, companies))
    except Exception as e:
        print(f"Could not fetch dynamic S&P 500 top 10. Using fallback. Error: {e}")
        return {
            'AAPL': 'Apple', 'MSFT': 'Microsoft', 'NVDA': 'Nvidia',
            'AMZN': 'Amazon', 'META': 'Meta', 'GOOGL': 'Alphabet',
            'BRK-B': 'Berkshire', 'AVGO': 'Broadcom', 'TSLA': 'Tesla', 'LLY': 'Eli Lilly'
        }


def calculate_indicators(df, currency="$"):
    """Modular indicator engine calculating changes and moving averages."""
    if df.empty or len(df) < 5:
        return None

    df = df.dropna(subset=['Close'])
    latest_price = df['Close'].iloc[-1]
    latest_date = df.index[-1]

    # --- 1. Price Formatting (No Emojis) ---
    if latest_price >= 1000:
        price_str = f"{currency}{latest_price:,.0f}"
    else:
        price_str = f"{currency}{latest_price:,.2f}"

    # --- Helper: Format Percentages with Emojis ---
    def format_pct(val):
        if pd.isna(val):
            return "⚪ N/A"
        if val > 0:
            return f"🟢 {val:+.1f}%"
        elif val < 0:
            return f"🔴 {val:+.1f}%"
        else:
            return f"⚪ {val:+.1f}%"

    # --- 2. 1D Change ---
    if len(df) >= 2:
        prev_close = df['Close'].iloc[-2]
        daily_pct = ((latest_price - prev_close) / prev_close) * 100
        pct_1d = format_pct(daily_pct)
    else:
        pct_1d = "⚪ N/A"

    def get_past_price(days_back):
        target = latest_date - pd.Timedelta(days=days_back)
        past = df.loc[df.index <= target, 'Close']
        return past.iloc[-1] if not past.empty else None

    def calc_pct(past_price):
        if past_price and past_price > 0:
            val = ((latest_price - past_price) / past_price) * 100
            return format_pct(val)
        return "⚪ N/A"

    # --- 3. Price Changes ---
    pct_1w = calc_pct(get_past_price(7))
    pct_1y = calc_pct(get_past_price(365))
    pct_2y = calc_pct(get_past_price(730))

    # --- 4. 200-Day Moving Average ---
    if len(df) >= 200:
        ma_200d = df['Close'].rolling(window=200).mean().iloc[-1]
        status_200d = "Abv" if latest_price > ma_200d else "Blw"
    else:
        status_200d = "N/A"

    # --- 5. 200-Week Moving Average ---
    weekly_closes = df['Close'].resample('W').last().dropna()
    if len(weekly_closes) >= 200:
        ma_200w = weekly_closes.rolling(window=200).mean().iloc[-1]
        status_200w = "Abv" if latest_price > ma_200w else "Blw"
    else:
        status_200w = "N/A"

    return {
        "Price": price_str,
        "1D": pct_1d,
        "1W": pct_1w,
        "1Y": pct_1y,
        "2Y": pct_2y,
        "200D MA": status_200d,
        "200W MA": status_200w,
    }


def fetch_asset_data(ticker_symbol):
    """Fetches 5 years of data with fallback handling for closed markets."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period="5y")
        if df.empty or len(df) < 5:
            df = ticker.history(period="max")
        return df
    except Exception:
        return pd.DataFrame()


def pad_field(text, target_visual_width):
    """Adjusts padding for strings containing emojis so visual column alignment stays exact in Discord."""
    has_emoji = any(e in text for e in ['🟢', '🔴', '⚪'])
    # Emojis take 2 monospace columns visually despite len() returning 1
    visual_len = len(text) + (1 if has_emoji else 0)
    padding_needed = max(0, target_visual_width - visual_len)
    return text + (" " * padding_needed)


def render_category_table(category_name, assets, currency="$"):
    """Generates a compact, perfectly aligned ASCII table block for Discord."""
    rows = []
    for ticker, name in assets.items():
        df = fetch_asset_data(ticker)

        # --- JSE WORKAROUND & DYNAMIC CURRENCY START ---
        # Set dynamic currency based on ticker origin to handle mixed-currency tables
        row_currency = currency
        if not df.empty and ticker.endswith('.JO'):
            df['Close'] = df['Close'] / 100  # Convert ZAC to ZAR
            row_currency = "R"  # Force Rand symbol for JSE assets
        # --- JSE WORKAROUND & DYNAMIC CURRENCY END ---

        data = calculate_indicators(df, currency=row_currency)

        if data:
            rows.append({
                "Asset": name[:10],
                "Price": data["Price"],
                "1D": data["1D"],
                "1W": data["1W"],
                "1Y": data["1Y"],
                "2Y": data["2Y"],
                "200D": data["200D MA"],
                "200W": data["200W MA"],
            })
        else:
            rows.append({
                "Asset": name[:10],
                "Price": "Err",
                "1D": "⚪ N/A",
                "1W": "⚪ N/A",
                "1Y": "⚪ N/A",
                "2Y": "⚪ N/A",
                "200D": "N/A",
                "200W": "N/A",
            })

    # Header Definition - Expanded width to account for 4 columns with emojis
    table_str = f"### {category_name}\n```text\n"
    table_str += (
        f"{'Asset':<10} | {'Price':<10} | {'1D':<10} | {'1W':<10} | "
        f"{'1Y':<10} | {'2Y':<10} | {'200D':<4} | {'200W':<4}\n"
    )
    table_str += (
        f"{'-' * 10}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 4}-+-{'-' * 4}\n"
    )

    for r in rows:
        asset_col = f"{r['Asset']:<10}"
        price_col = f"{r['Price']:<10}"
        d1_col = pad_field(r['1D'], 10)
        w1_col = pad_field(r['1W'], 10)
        y1_col = pad_field(r['1Y'], 10)
        y2_col = pad_field(r['2Y'], 10)
        d200_col = f"{r['200D']:<4}"
        w200_col = f"{r['200W']:<4}"

        table_str += (
            f"{asset_col} | {price_col} | {d1_col} | {w1_col} | "
            f"{y1_col} | {y2_col} | {d200_col} | {w200_col}\n"
        )

    table_str += "```\n"
    return table_str


def send_webhook(chunks, webhook_url=None):
    """Pushes chunks to Discord."""
    url = webhook_url or DISCORD_WEBHOOK_URL
    if not url:
        print("⚠️ No Webhook URL configured in .env. Terminal Output:\n")
        for chunk in chunks:
            print(chunk)
        return

    for chunk in chunks:
        try:
            res = requests.post(url, json={"content": chunk}, timeout=10)
            if res.status_code not in (200, 204):
                print(f"Failed to post chunk to Discord. HTTP Status: {res.status_code}")
        except Exception as e:
            print(f"Error sending webhook chunk: {e}")


def main():
    date_str = datetime.now().strftime('%A, %B %d, %Y')
    print("Fetching dynamic data and building tables...")

    # Asset Definitions
    indices = {
        '^GSPC': 'S&P 500',
        '^IXIC': 'NASDAQ 100',
        '^DJI': 'Dow Jones',
        'URTH': 'MSCI World',  # iShares MSCI World ETF proxy
        'VT': 'Global ETF',  # Vanguard Total World (Proxy for Global 1200)
        '^J203.JO': 'JSE AllShare'
    }

    commodities = {
        'GC=F': 'Gold',
        'SI=F': 'Silver',
        'CL=F': 'Crude Oil',
        'HG=F': 'Copper'
    }

    crypto = {
        'BTC-USD': 'Bitcoin',
        'ETH-USD': 'Ethereum',
        'ZEC-USD': 'ZCash'
    }

    jse_portfolio = {
        '4SI.JO': '4Sight',
        'BAC.JO': 'Afr Bitcoin',
        'AFT.JO': 'Afrimat',
        'ISO.JO': 'ASP Isotopes',
        'BCF.JO': 'Bowler Met',
        'CAA.JO': 'CA Sales',
        'DNB.JO': 'Deneb Inv',
        'FTH.JO': 'Frontier Tr',
        'LSK.JO': 'Lesaka Tech',
        'PBT.JO': 'PBT Holdings',
        'SKA.JO': 'Shuka Min'
    }

    us_portfolio = {
        'REXR': 'REXR',
        'JD': 'JD.com',
        'STRK': 'Strategy 8%'
    }

    top_10_sp500 = get_dynamic_sp500_top10()

    t1 = render_category_table("Major Indices", indices, currency="$")
    t2 = render_category_table("Commodities", commodities, currency="$")
    t3 = render_category_table("Crypto Assets", crypto, currency="$")
    t4 = render_category_table("Top 10 S&P 500 Stocks", top_10_sp500, currency="$")
    t5 = render_category_table("JSE Portfolio", jse_portfolio, currency="R")
    t6 = render_category_table("US Portfolio", us_portfolio, currency="$")

    header = f"## Comprehensive Market Dashboard\n*{date_str}*\n\n"

    messages = [
        header + t1 + t2,
        t3 + t4,
        t5 + t6
    ]

    send_webhook(messages, webhook_url=DISCORD_WEBHOOK_URL)
    print("Successfully dispatched market table update.")


if __name__ == "__main__":
    main()