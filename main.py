import yfinance as yf
import requests
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

# Securely load the webhook from the environment
WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')


def get_market_data(tickers_dict):
    """Fetches 2-day historical data and calculates percentage change."""
    results = []
    tickers = list(tickers_dict.keys())

    # Download all tickers at once to speed up the script
    data = yf.download(tickers, period="2d", group_by='ticker', progress=False)

    for ticker in tickers:
        name = tickers_dict[ticker]
        try:
            # Handle yfinance data structures (varies based on single vs multiple tickers)
            if len(tickers) == 1:
                hist = data
            else:
                hist = data[ticker]

            # Drop missing values (in case a market was closed)
            hist = hist.dropna()

            if len(hist) >= 2:
                close_today = hist['Close'].iloc[-1]
                close_yest = hist['Close'].iloc[-2]
                change_pct = ((close_today - close_yest) / close_yest) * 100

                # Visual indicators
                emoji = "🟩" if change_pct >= 0 else "🟥"

                # Format price differently based on asset size
                if close_today > 1000:
                    price_str = f"{close_today:,.0f}"
                else:
                    price_str = f"{close_today:,.2f}"

                results.append(f"{emoji} **{name}**: {price_str} ({change_pct:+.2f}%)")
            else:
                results.append(f"⚠️ **{name}**: Market Closed / No Data")
        except Exception:
            results.append(f"⚠️ **{name}**: Error fetching data")

    return results


def get_google_news():
    """Scrapes the top financial headline from Google News RSS."""
    try:
        # Search query for "Stock Market" top news in the US
        rss_url = "https://news.google.com/rss/search?q=stock+market+finance&hl=en-US&gl=US&ceid=US:en"

        # Add a user-agent so Google doesn't block the automated request
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()

        # Parse the XML to grab the first <item> (top story)
        root = ET.fromstring(xml_data)
        first_item = root.find('./channel/item')

        if first_item is not None:
            title = first_item.find('title').text
            link = first_item.find('link').text
            return f"📰 **Top Market Story:** [{title}]({link})"

    except Exception as e:
        print(f"News fetch error: {e}")
        pass

    return "📰 **Top Market Story:** Unavailable today."


def main():
    # 1. Define Asset Classes
    indices = {
        '^GSPC': 'S&P 500',
        '^IXIC': 'NASDAQ',
        '^DJI': 'Dow Jones',
        '^RUT': 'Russell 2000'
    }

    commodities = {
        'GC=F': 'Gold',
        'SI=F': 'Silver',
        'CL=F': 'Crude Oil'
    }

    movers = {
        'NVDA': 'Nvidia',
        'TSLA': 'Tesla',
        'AAPL': 'Apple'
    }

    # 2. Construct the Discord message
    date_str = datetime.now().strftime('%A, %B %d, %Y')
    message = f"## 📊 Daily Market Briefing - {date_str}\n\n"

    message += "**🏦 Major Indices:**\n"
    for line in get_market_data(indices):
        message += f"{line}\n"

    message += "\n**🛢️ Commodities:**\n"
    for line in get_market_data(commodities):
        message += f"{line}\n"

    message += "\n**💻 Tech Movers:**\n"
    for line in get_market_data(movers):
        message += f"{line}\n"

    # 3. Add the Top News Headline
    message += f"\n{get_google_news()}\n\n"
    message += "_Automated exclusively for Patrons._ 💙"

    # 4. Push to Discord
    if WEBHOOK_URL:
        payload = {"content": message}
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("Successfully posted to Discord!")
        else:
            print(f"Failed to post: {response.status_code} - {response.text}")
    else:
        print("⚠️ ERROR: Discord Webhook URL not found.")
        print("Draft Output:\n")
        print(message)


if __name__ == "__main__":
    main()