"""Sample data for the exploring-skill examples — self-contained, offline.

`sample_fremont()` synthesizes Fremont Bridge hourly bicycle counts with the
real structure: commute peaks, weekday/weekend regimes, summer seasonality, a
multi-year uptick, weather wobble, and a directional split. Swap it for the real
CSV (data.seattle.gov "Fremont Bridge Hourly Bicycle Counts") when you have it.
"""

import numpy as np
import pandas as pd


def sample_fremont(seed=42):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2014-01-01", "2018-12-31 23:00", freq="h")
    hour, dow, doy, year = (
        idx.hour.values,
        idx.dayofweek.values,
        idx.dayofyear.values,
        idx.year.values,
    )
    weekend = dow >= 5
    commute = np.exp(-((hour - 8) ** 2) / (2 * 1.4**2)) + np.exp(
        -((hour - 17.5) ** 2) / (2 * 1.4**2)
    )
    midday = np.exp(-((hour - 13) ** 2) / (2 * 3.0**2))
    shape = np.where(weekend, 0.8 * midday, commute + 0.12 * midday)
    seasonal = 0.70 + 0.30 * np.cos(2 * np.pi * (doy - 200) / 365)
    trend = 1 + 0.07 * (year - 2014)
    daykey = idx.normalize().asi8
    r2 = np.random.default_rng(seed + 1)
    rain = np.array(
        [{d: (0.5 if r2.random() < 0.28 else 1.0) for d in np.unique(daykey)}[d] for d in daykey]
    )
    total = rng.poisson(np.clip(75 * shape * seasonal * trend * rain, 0, None))
    east = rng.binomial(total, np.where(hour < 12, 0.63, 0.37))
    df = pd.DataFrame({"East": east, "West": total - east, "Total": total}, index=idx)
    df.index.name = "Date"
    return df
