import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from scipy.stats import mannwhitneyu
import warnings
warnings.filterwarnings("ignore")

# ===============================
# CONFIG
# ===============================
DATA_PATH = "../data/"
OUTPUT_PATH = "../outputs/"

SENTIMENT_FILE = "fear_greed_index.csv"
TRADER_FILE = "historical_data.csv"


# ===============================
# LOAD & CLEAN DATA
# ===============================
def load_and_clean_data():

    print("=" * 80)
    print("LOADING AND CLEANING DATA")
    print("=" * 80)

    # ---------- Load sentiment ----------
    sentiment_df = pd.read_csv(DATA_PATH + SENTIMENT_FILE)

    sentiment_df["date"] = pd.to_datetime(sentiment_df["date"]).dt.normalize()
    sentiment_df = sentiment_df.dropna(subset=["classification"])
    sentiment_df["classification"] = (
        sentiment_df["classification"].str.strip().str.title()
    )

    def map_sentiment(row):
        if "Fear" in row["classification"]:
            return "Fear"
        elif "Greed" in row["classification"]:
            return "Greed"
        else:
            if row["value"] < 45:
                return "Fear"
            elif row["value"] > 55:
                return "Greed"
            else:
                return "Neutral"

    sentiment_df["sentiment_binary"] = sentiment_df.apply(map_sentiment, axis=1)

    print("Sentiment data loaded:", sentiment_df.shape)
    print("Sentiment range:", sentiment_df["date"].min(), "→", sentiment_df["date"].max())
    print(sentiment_df["sentiment_binary"].value_counts())

    # ---------- Load trader ----------
    trader_df = pd.read_csv(DATA_PATH + TRADER_FILE)

    # normalize column names
    trader_df.columns = (
        trader_df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    if "timestamp_ist" not in trader_df.columns:
        raise ValueError("timestamp_ist column missing in trader data")

    trader_df["trade_time"] = pd.to_datetime(
        trader_df["timestamp_ist"],
        format="%d-%m-%Y %H:%M",
        errors="coerce"
    )

    trader_df["trade_date"] = trader_df["trade_time"].dt.normalize()

    trader_df["closed_pnl"] = pd.to_numeric(
        trader_df.get("closed_pnl", 0), errors="coerce"
    ).fillna(0)

    trader_df["size_usd"] = pd.to_numeric(
        trader_df.get("size_usd", 0), errors="coerce"
    ).fillna(0)

    trader_df["fee"] = pd.to_numeric(
        trader_df.get("fee", 0), errors="coerce"
    ).fillna(0)

    print("Trader data loaded:", trader_df.shape)
    print("Trader date range:",
          trader_df["trade_date"].min(), "→", trader_df["trade_date"].max())
    print("Unique traders:", trader_df["account"].nunique())

    # ---------- Merge ----------
    merged_df = trader_df.merge(
        sentiment_df[["date", "sentiment_binary"]],
        left_on="trade_date",
        right_on="date",
        how="inner"
    )

    merged_df = merged_df[
        merged_df["sentiment_binary"].isin(["Fear", "Greed"])
    ]

    print("Merged dataset:", merged_df.shape)
    print(merged_df["sentiment_binary"].value_counts())

    if merged_df.empty:
        raise ValueError("Merged dataframe is EMPTY. Date mismatch issue.")

    return merged_df, sentiment_df


# ===============================
# DAILY METRICS
# ===============================
def create_daily_metrics(merged_df):

    print("\n" + "=" * 80)
    print("CREATING DAILY METRICS")
    print("=" * 80)

    grouped = merged_df.groupby(
        ["account", "trade_date", "sentiment_binary"]
    )

    daily_metrics = grouped.agg({
        "closed_pnl": ["sum", "mean", "std", "count"],
        "size_usd": ["sum", "mean"],
        "fee": "sum"
    }).reset_index()

    daily_metrics.columns = [
        "account",
        "trade_date",
        "sentiment_binary",
        "daily_pnl",
        "avg_pnl_per_trade",
        "pnl_volatility",
        "num_trades",
        "total_volume",
        "avg_trade_size",
        "total_fees"
    ]

    # BUY ratio
    buy_ratio = (
        merged_df
        .groupby(["account", "trade_date"])["side"]
        .apply(lambda x: (x == "BUY").mean())
        .reset_index(name="buy_ratio")
    )

    # Win rate
    win_rate = (
        merged_df
        .groupby(["account", "trade_date"])["closed_pnl"]
        .apply(lambda x: (x > 0).mean())
        .reset_index(name="win_rate")
    )

    daily_metrics = daily_metrics.merge(
        buy_ratio, on=["account", "trade_date"], how="left"
    )

    daily_metrics = daily_metrics.merge(
        win_rate, on=["account", "trade_date"], how="left"
    )

    daily_metrics["pnl_volatility"] = daily_metrics["pnl_volatility"].fillna(0)
    daily_metrics["net_pnl"] = (
        daily_metrics["daily_pnl"] - daily_metrics["total_fees"]
    )

    print("Daily metrics shape:", daily_metrics.shape)

    return daily_metrics


# ===============================
# STATISTICS
# ===============================
def statistical_analysis(daily_metrics):

    print("\n" + "=" * 80)
    print("STATISTICAL ANALYSIS")
    print("=" * 80)

    fear = daily_metrics[daily_metrics["sentiment_binary"] == "Fear"]["daily_pnl"]
    greed = daily_metrics[daily_metrics["sentiment_binary"] == "Greed"]["daily_pnl"]

    stat, p = mannwhitneyu(fear, greed, alternative="two-sided")

    print("Mann-Whitney U Test (Daily PnL)")
    print("U:", stat)
    print("P-value:", p)

    print("\nMeans:")
    print("Fear mean:", fear.mean())
    print("Greed mean:", greed.mean())


# ===============================
# EXPORT
# ===============================
def export_results(daily_metrics):

    print("\n" + "=" * 80)
    print("EXPORTING RESULTS")
    print("=" * 80)

    daily_metrics.to_csv(
        OUTPUT_PATH + "daily_trader_metrics.csv",
        index=False
    )

    summary = daily_metrics.groupby("sentiment_binary").mean(numeric_only=True)
    summary.to_csv(OUTPUT_PATH + "sentiment_summary.csv")

    print("Files saved in:", OUTPUT_PATH)


# ===============================
# MAIN
# ===============================
def main():

    print("=" * 80)
    print("TRADER SENTIMENT ANALYSIS")
    print("=" * 80)
    print("Start:", datetime.now())

    merged_df, sentiment_df = load_and_clean_data()
    daily_metrics = create_daily_metrics(merged_df)
    statistical_analysis(daily_metrics)
    export_results(daily_metrics)

    print("\nEND:", datetime.now())
    print("DONE.")


if __name__ == "__main__":
    main()
