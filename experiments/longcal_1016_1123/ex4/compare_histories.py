"""Compare the two frozen horizons on exactly paired held-out marker/axis/night cells."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def paired(path):
    df = pd.read_csv(path / "per_cell.csv.gz", dtype={"device": str, "marker": str})
    keys = ["line", "device", "marker", "axis", "night"]
    return df.loc[df.split == "test"].set_index(keys, verify_integrity=True).sort_index()


def stats(baseline, long, short):
    delta = short - long
    return {
        "cells": len(delta), "v53_mean_variance_mm2": float(baseline.mean()),
        "ex1_mean_variance_mm2": float(long.mean()), "ex4_mean_variance_mm2": float(short.mean()),
        "ex1_extra_reduction_vs_v53_percentage_points":
            float(100 * delta.mean() / baseline.mean()) if baseline.mean() else None,
        "cells_favoring_30_days": int((delta > 1e-12).sum()),
        "cells_favoring_3_days": int((delta < -1e-12).sum()),
        "cells_tied_at_1e_minus_12_mm2": int((np.abs(delta) <= 1e-12).sum())
    }


def compare(source, ablated):
    long, short = paired(source), paired(ablated)
    if not len(long) or not long.index.equals(short.index):
        raise ValueError("Test cohort mismatch between ex1 and ex4")
    for column in ["var0", "count", "adjacent", "spikes0", "anchors", "abs0", "sq0"]:
        if not np.array_equal(long[column], short[column]):
            raise ValueError("Baseline/input mismatch in " + column)
    result = {"all": stats(long.var0, long.var1, short.var1)}
    for key in ["axis", "line"]:
        for label, group in long.groupby(level=key):
            result[label] = stats(group.var0, group.var1, short.loc[group.index, "var1"])
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ex1-results", type=Path, required=True)
    p.add_argument("--ex4-results", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.write_text(json.dumps(compare(a.ex1_results, a.ex4_results), indent=2,
                                allow_nan=False) + "\n", encoding="utf-8")
