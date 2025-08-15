from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool
from bokeh.palettes import Category10
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import feedparser
import os
from datetime import datetime


# Load CSS based on theme
def load_css(theme="light"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    css_file = os.path.join(base_dir, f"{theme}.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Moving average strategy
def generate_signals(data, short_window, long_window):
    data['Short_MA'] = data['Close'].rolling(window=short_window).mean()
    data['Long_MA'] = data['Close'].rolling(window=long_window).mean()
    data['Signal'] = 0
    data.loc[data.index[short_window:], 'Signal'] = (
        (data['Short_MA'][short_window:] > data['Long_MA'][short_window:]).astype(int)
    )
    data['Position'] = data['Signal'].diff()
    return data

# Backtest
def backtest(data, initial_investment=100000):
    data['Daily_Return'] = data['Close'].pct_change()
    data['Strategy_Return'] = data['Daily_Return'] * data['Signal'].shift(1)
    data['Portfolio_Value'] = (1 + data['Strategy_Return']).cumprod() * initial_investment

    max_value = data['Portfolio_Value'].cummax()
    drawdown = (data['Portfolio_Value'] - max_value) / max_value
    max_drawdown = drawdown.min()

    total_return = data['Portfolio_Value'].iloc[-1] / initial_investment - 1
    num_years = (data.index[-1] - data.index[0]).days / 365.25
    cagr = ((1 + total_return) ** (1 / num_years)) - 1 if num_years > 0 else 0

    return cagr * 100, max_drawdown * 100, total_return * 100, data['Portfolio_Value'].iloc[-1]

# News
def fetch_news_sentiment(ticker):
    url = f"https://news.google.com/rss/search?q={ticker}+stock"
    feed = feedparser.parse(url)
    headlines = []
    for entry in feed.entries[:5]:
        title = entry.title
        summary = getattr(entry, 'summary', '')
        link = getattr(entry, 'link', '')
        published = getattr(entry, 'published', 'N/A')
        sentiment = "Positive" if any(word in title.lower() for word in ["gain", "up", "rise", "soar"]) else \
                    "Negative" if any(word in title.lower() for word in ["fall", "down", "drop", "loss"]) else "Neutral"
        headlines.append({
            "title": title,
            "summary": summary,
            "published": published,
            "sentiment": sentiment,
            "link": link
        })
    return pd.DataFrame(headlines)

# Main app
def main():
    load_css('light')

    st.set_page_config(layout="wide")

    with st.sidebar:
        st.header("Settings")
        ticker = st.text_input("Enter Stock Ticker", value="AAPL").upper()
        start_date = st.date_input("Start Date", value=date.today() - timedelta(days=365))
        end_date = st.date_input("End Date", value=date.today())
        short_window = st.number_input("Short MA Window", min_value=1, value=20)
        long_window = st.number_input("Long MA Window", min_value=1, value=50)
        initial_investment = st.number_input("Initial Investment (₹)", min_value=1000, value=100000)
        theme = st.selectbox("Choose Theme", ["light", "dark"])

        # Spacer to push footer to bottom
        st.markdown("<div style='flex:1;'></div>", unsafe_allow_html=True)
    
        # Sidebar footer
        st.markdown("""
        <div style="
            position: fixed;
            bottom: 10px;
            width: inherit;
            text-align: center;
            font-size: 13px;
            color: #ccc;
        ">
            <strong>Klaymatrix Data Lab</strong><br>
        </div>
        """, unsafe_allow_html=True)


    load_css(theme)

    st.markdown(
        f"<h2 style='text-align: center;'>Strategy BackTester: <span style='color: #007BFF;'>{ticker}</span></h2>",
        unsafe_allow_html=True
    )

    df = yf.download(ticker, start=start_date, end=end_date)
    df.columns = df.columns.droplevel(1)
    if df.empty:
        st.error("Failed to fetch stock data.")
        return

    df = generate_signals(df, short_window, long_window)
    cagr, max_dd, total_return, final_value = backtest(df, initial_investment)

    #st.subheader("📊 Strategy Metrics")
    metrics = [
        ("CAGR", f"{cagr:.2f}%"),
        ("Max Drawdown", f"{max_dd:.2f}%"),
        ("Total Return", f"{total_return:.2f}%"),
        ("Final Portfolio Value", f"₹{final_value:,.2f}")
    ]
    
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics):
        col.markdown(
            f"""
            <div class="metric-card">
                <h3>{label}</h3>
                <p>{value}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Bokeh plot
    p = figure(width=900, height=500, x_axis_type="datetime", title=f"{ticker} Price & Moving Averages",toolbar_location=None)

    p.line(df.index, df['Close'], color="#5C7AFF", legend_label="Close Price")

#    p.line(df.index, df['Close'], color="blue", legend_label="Close Price")
    p.line(df.index, df['Short_MA'], color="green", line_dash="dashed", legend_label=f"Short MA ({short_window})")
    p.line(df.index, df['Long_MA'], color="purple", line_dash="dashed", legend_label=f"Long MA ({long_window})")

    # Buy/Sell markers (updated for Bokeh 3.2.1)
    buys = df[df['Position'] == 1]
    sells = df[df['Position'] == -1]
    p.scatter(buys.index, buys['Close'], size=10, color="green", marker="triangle", legend_label="Buy Signal")
    p.scatter(sells.index, sells['Close'], size=10, color="red", marker="inverted_triangle", legend_label="Sell Signal")

    p.legend.location = "top_left"
    p.xaxis.axis_label = "Date"
    p.yaxis.axis_label = "Price"
    p.add_tools(HoverTool(tooltips=[("Date", "@x{%F}"), ("Price", "@y")], formatters={'@x': 'datetime'}))

    
    # Add hover tooltip above chart
    st.markdown("""
    <style>
    .tooltip {
      position: relative;
      display: block;
      text-align: left; 
      margin-bottom: 10px;
      margin-top: 10px;
      font-size: 12px;
      cursor: help;
    }
    
    .tooltip .tooltiptext {
      visibility: hidden;
      width: 600px;
      background-color: #ccdbfd;
      color: #fff;
      text-align: left;
      border-radius: 6px;
      padding: 8px;
      position: absolute;
      z-index: 1;
      top: 30px; /* Position below the icon */
      left: 25%;
      transform: translateX(-50%); /* Keep tooltip centered */
      opacity: 0;
      transition: opacity 0.3s;
    }
    
    .tooltip:hover .tooltiptext {
      visibility: visible;
      opacity: 1;
    }
    </style>
    
    <div class="tooltip">ℹ️ About this strategy
        <span class="tooltiptext">
          The Golden Cross strategy is a bullish technical pattern used in stock trading.<br><br>
          It occurs when a short-term moving average (blue line) crosses above a long-term moving average (orange line), often interpreted as a sign of a potential uptrend.<br><br>
          This crossover indicates that short-term momentum is strengthening and may lead to a sustained upward price movement.<br><br>
          The opposite pattern is called the Death Cross. It occurs when the short-term moving average crosses below the long-term moving average, signaling potential downward momentum and a possible sustained price decline.<br><br>
          Green triangles mark buy signals (Golden Cross), and red inverted triangles mark sell signals (Death Cross).
        </span>
    </div>
    """, unsafe_allow_html=True)



    st.bokeh_chart(p, use_container_width=True)

    # show the exact data that feeds the chart
    st.caption("Data Used")
    with st.expander(""):
        df_display = df.reset_index()
        # Ensure the first column is named 'Date' for clarity
        if 'Date' not in df_display.columns:
            df_display.rename(columns={df_display.columns[0]: 'Date'}, inplace=True)
        cols = ['Date', 'Close', 'Short_MA', 'Long_MA', 'Signal', 'Position']
        present_cols = [c for c in cols if c in df_display.columns]
        st.dataframe(df_display[present_cols].tail(300), use_container_width=True)


    st.subheader("📰 News Sentiment")
    
    # Legend
    st.markdown("""
    <div class="sentiment-legend">
      <div class="sentiment-item"><span class="sentiment-circle circle-positive"></span>Positive</div>
      <div class="sentiment-item"><span class="sentiment-circle circle-negative"></span>Negative</div>
      <div class="sentiment-item"><span class="sentiment-circle circle-neutral"></span>Neutral</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Fetch news
    news_df = fetch_news_sentiment(ticker)
    
    for _, row in news_df.iterrows():
        # Try to remove time portion if it exists
        published_date = str(row['published'])
 
    
        # Sentiment color class mapping
        sentiment_class = {
            "Positive": "circle-positive",
            "Negative": "circle-negative",
            "Neutral": "circle-neutral"
        }.get(row['sentiment'], "circle-neutral")
    
        # Render news item
        st.markdown(
            f"""
            <div style="margin-bottom:10px;">
                <span class="sentiment-circle {sentiment_class}"></span>
                <a href="{row['link']}" target="_blank"><strong>{row['title']}</strong></a><br>
                <small><i>{published_date}</i></small><br>
                <div style="font-size: 90%; color: gray;">{row['summary'][:120]}...</div>
            </div>
            """,
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()







