import yfinance as yf
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Securely load the webhook from the environment
WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')


def get_market_data(tickers, names):
    """Fetches 2-day historical data and calculates percentage change."""
    results = []
    for ticker in tickers:
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="2d")
            if len(hist) >= 2:
                close_today = hist['Close'].iloc[-1]
                close_yest = hist['Close'].iloc[-2]
                change_pct = ((close_today - close_yest) / close_yest) * 100

                # Visual indicators
                emoji = "🟩" if change_pct >= 0 else "🟥"
                results.append(f"{emoji} **{names[ticker]}**: ${close_today:,.2f} ({change_pct:+.2f}%)")
        except Exception:
            results.append(f"⚠️ Error fetching data for {names[ticker]}")
    return results


def get_top_news(ticker="SPY"):
    """Pulls the latest news headline for a given ticker."""
    try:
        data = yf.Ticker(ticker)
        news = data.news
        if news and len(news) > 0:
            title = news[0].get('title', 'No title available')
            link = news[0].get('link', '#')
            return f"📰 **Top Story:** [{title}]({link})"
    except Exception:
        pass
    return "📰 **Top Story:** Unavailable today."


def main():
    # Define the assets you want to track
    indexes = ['^GSPC', '^IXIC', 'BTC-USD']
    index_names = {'^GSPC': 'S&P 500', '^IXIC': 'NASDAQ', 'BTC-USD': 'Bitcoin'}

    movers = ['NVDA', 'TSLA', 'AAPL']
    mover_names = {'NVDA': 'Nvidia', 'TSLA': 'Tesla', 'AAPL': 'Apple'}

    # Construct the Discord message
    date_str = datetime.now().strftime('%A, %B %d, %Y')
    message = f"## 📊 Daily Market Briefing - {date_str}\n\n"

    message += "**Macro Overview:**\n"
    for line in get_market_data(indexes, index_names):
        message += f"{line}\n"

    message += "\n**Tech Movers:**\n"
    for line in get_market_data(movers, mover_names):
        message += f"{line}\n"

    message += f"\n{get_top_news('SPY')}\n\n"
    message += "_Automated exclusively for Patrons._ 💙"

    # Push to Discord
    if WEBHOOK_URL:
        payload = {"content": message}
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("Successfully posted to Discord!")
        else:
            print(f"Failed to post: {response.status_code} - {response.text}")
    else:
        print("⚠️ ERROR: Discord Webhook URL not found in environment variables.")
        print("Here is the draft of what would have been sent:\n")
        print(message)


if __name__ == "__main__":
    main()