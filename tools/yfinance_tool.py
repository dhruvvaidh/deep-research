"""LangChain tool for pulling financial data via yfinance."""
import yfinance as yf
from langchain_core.tools import tool


@tool
def yfinance_data(ticker: str, period: str = "1y") -> str:
    """Retrieve financial data for a stock ticker and save it as a CSV in the sandbox.

    The raw OHLCV DataFrame is saved to disk immediately — raw data is never returned
    to the context window.  Pass the returned CSV path to code_executor to analyse it.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL", "MSFT").
        period: Data period — one of: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max.

    Returns:
        A brief metadata summary plus the sandbox CSV path for code_executor.
    """
    from tools.context_store import save_dataset

    stock = yf.Ticker(ticker)
    info = stock.info
    hist = stock.history(period=period)

    name = info.get("longName", ticker)
    market_cap = info.get("marketCap")
    cap_str = f"${market_cap:,.0f}" if market_cap else "N/A"

    if hist.empty:
        return f"{ticker.upper()}: no price history available for period '{period}'."

    # Save raw OHLCV data as CSV — code_executor reads it by path
    key = f"{ticker.lower()}_{period}_ohlcv"
    csv_content = hist.to_csv()
    csv_path = save_dataset.func(
        key=key,
        csv_content=csv_content,
        description=f"{ticker.upper()} OHLCV data, period={period}",
    )

    latest_close = hist["Close"].iloc[-1]
    rows = len(hist)

    return (
        f"{ticker.upper()} ({name})\n"
        f"Market Cap: {cap_str} | P/E: {info.get('trailingPE', 'N/A')}\n"
        f"52w High: {info.get('fiftyTwoWeekHigh', 'N/A')} | 52w Low: {info.get('fiftyTwoWeekLow', 'N/A')}\n"
        f"Latest close: {latest_close:.2f} | {rows} rows ({period})\n"
        f"CSV saved → {csv_path}\n"
        f"Pass this path to code_executor to analyse the data."
    )
