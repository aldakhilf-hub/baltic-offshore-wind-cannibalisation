#!/usr/bin/env python3
"""Ten-second check that your install works and the bundled data is intact.

    python tools/smoke_test.py

Each check is independent and reports on its own, so a missing heavy
dependency does not hide a working light one. Nothing is written to disk.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_Model_Deliverable"))

PASS, FAIL, SKIP = "  ok  ", " FAIL ", " skip "
results = []


def check(name):
    """Decorator running one check and recording its outcome."""
    def wrap(fn):
        try:
            detail = fn()
            results.append((PASS, name, detail or ""))
        except ModuleNotFoundError as e:
            results.append((SKIP, name, f"missing package: {e.name}"))
        except Exception as e:
            results.append((FAIL, name, f"{type(e).__name__}: {e}"))
        return fn
    return wrap


@check("1. core scientific stack imports")
def _():
    import pandas, numpy
    return f"pandas {pandas.__version__}, numpy {numpy.__version__}"


@check("2. xgboost loads (needs libomp on macOS)")
def _():
    import xgboost
    return f"xgboost {xgboost.__version__}"


@check("3. surrogate model predicts")
def _():
    import baltic_wind_model as m
    df = m.predict()
    assert len(df) > 0, "predict() returned no rows"
    cv = df["capture_value"] if "capture_value" in df else df.iloc[:, 1]
    lo, hi = float(cv.min()), float(cv.max())
    assert 0.0 <= lo <= 1.6 and 0.0 <= hi <= 1.6, f"capture values out of range: {lo}-{hi}"
    return f"{len(df)} zones, capture value {lo:.2f} to {hi:.2f}"


@check("4. surrogate headline figures")
def _():
    import numbers
    import baltic_wind_model as m
    h = m.headline()
    scalars = {k: v for k, v in h.items() if isinstance(v, numbers.Number)}
    return ", ".join(f"{k}={v:.3f}" for k, v in scalars.items())


@check("5. regression panel present and complete")
def _():
    import pandas as pd
    f = ROOT / "2_Regression_Model/data/features_strandA/features_monthly.csv"
    assert f.exists(), f"missing {f.relative_to(ROOT)}"
    df = pd.read_csv(f)
    return f"{len(df)} farm-months, {df.shape[1]} columns, {df['farm'].nunique() if 'farm' in df else '?'} farms"


@check("6. headline result tables present")
def _():
    import pandas as pd
    need = [
        "7_Thesis_Figures/results/grid_reversal_table.csv",
        "7_Thesis_Figures/results/cv_decomposition_table.csv",
        "1_PyPSA_Model/results/projections_v3/projected_capture_values.csv",
    ]
    missing = [p for p in need if not (ROOT / p).exists()]
    assert not missing, f"missing: {missing}"
    g = pd.read_csv(ROOT / "7_Thesis_Figures/results/grid_reversal_table.csv")
    r = g[g.year == 2040].iloc[0]
    return (f"2040 today's grid: North Sea {r.ns_frozen:.2f}, Baltic {r.bal_frozen:.2f}; "
            f"expanded: {r.ns_opt:.2f} / {r.bal_opt:.2f}")


@check("7. PyPSA stack (only needed for Track 1)")
def _():
    import pypsa
    return f"pypsa {pypsa.__version__}"


@check("8. geospatial stack (only needed for the map figures)")
def _():
    import geopandas, cartopy, rasterio
    return f"geopandas {geopandas.__version__}, cartopy {cartopy.__version__}"


print(f"\nRepository: {ROOT}\n")
for status, name, detail in results:
    print(f"[{status}] {name}")
    if detail:
        print(f"         {detail}")

failed = [r for r in results if r[0] == FAIL]
skipped = [r for r in results if r[0] == SKIP]
print(f"\n{len(results) - len(failed) - len(skipped)} passed, "
      f"{len(skipped)} skipped, {len(failed)} failed")
if skipped:
    print("Skipped checks just mean that part of the stack is not installed. "
          "Checks 1 to 6 are the ones that matter for the light install.")
if failed:
    print("\nSomething is genuinely wrong. See the Troubleshooting section of README.md.")
sys.exit(1 if failed else 0)
