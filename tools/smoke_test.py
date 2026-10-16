#!/usr/bin/env python3
"""Ten-second check that your install works and the bundled data is intact.

    python tools/smoke_test.py

Each check runs on its own and reports on its own, so a missing heavy
dependency does not hide a working light one. Nothing is written to disk.

Checks 1 to 5 are all you need for the regression model. Checks 6 to 8 cover
the figure and map scripts. Check 9 covers re-solving the power system model.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

PASS, FAIL, SKIP = "  ok  ", " FAIL ", " skip "
results = []


def check(name):
    """Decorator running one check and recording its outcome."""
    def wrap(fn):
        try:
            detail = fn()
            results.append((PASS, name, detail or ""))
        except ModuleNotFoundError as e:
            results.append((SKIP, name, f"not installed: {e.name}"))
        except Exception as e:
            results.append((FAIL, name, f"{type(e).__name__}: {e}"))
        return fn
    return wrap


# ---------------------------------------------------------------- regression

@check("1. core scientific stack")
def _():
    import pandas, numpy, sklearn
    return (f"pandas {pandas.__version__}, numpy {numpy.__version__}, "
            f"scikit-learn {sklearn.__version__}")


@check("2. xgboost loads (needs libomp on macOS)")
def _():
    import xgboost
    return f"xgboost {xgboost.__version__}"


@check("3. regression panel present and complete")
def _():
    import pandas as pd
    f = ROOT / "2_Regression_Model/data/features_strandA/features_monthly.csv"
    assert f.exists(), f"missing {f.relative_to(ROOT)}"
    df = pd.read_csv(f)
    # the seven features, named as 2.06_fit_regression.py expects them
    feats = ["feature_1_Corr_VRE", "feature_2_Corr_Load",
             "feature_3_VRE_MarketShare", "feature_4_Gas_Price",
             "feature_5_Carbon_Price", "feature_6_Flexibility_Index",
             "feature_7_Interconnection_Index"]
    missing = [c for c in feats if c not in df.columns]
    assert not missing, f"missing feature columns: {missing}"
    nulls = int(df[feats].isna().sum().sum())
    farms = df["farm"].nunique() if "farm" in df else "?"
    return (f"{len(df)} farm-months, {farms} farms, "
            f"all 7 features present, {nulls} missing values")


@check("4. observed capture values present")
def _():
    import pandas as pd
    f = ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv"
    assert f.exists(), f"missing {f.relative_to(ROOT)}"
    df = pd.read_csv(f)
    col = "CV" if "CV" in df else "capture_value"
    return f"{len(df)} rows, capture value {df[col].min():.2f} to {df[col].max():.2f}"


@check("5. recorded regression result reads back")
def _():
    import pandas as pd
    f = ROOT / "2_Regression_Model/results/01_model_fit_and_validation/regression_metrics.csv"
    assert f.exists(), f"missing {f.relative_to(ROOT)}"
    m = pd.read_csv(f)
    xgb = m[m.model == "XGBoost"].set_index("split").R2
    farm_out = xgb.get("GroupKFold(farm)")
    random_k = xgb.get("RandomKFold (Paul protocol)")
    return (f"leave-farm-out {farm_out:.3f}, random split {random_k:.3f} "
            f"(re-running 2.06 should reproduce these)")


# ------------------------------------------------------------------- figures

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
    return (f"2040 on today's grid: North Sea {r.ns_frozen:.2f}, Baltic {r.bal_frozen:.2f}; "
            f"with the grid built: {r.ns_opt:.2f} / {r.bal_opt:.2f}")


@check("7. geospatial stack (needed for the maps)")
def _():
    import geopandas, cartopy, rasterio
    return (f"geopandas {geopandas.__version__}, cartopy {cartopy.__version__}, "
            f"rasterio {rasterio.__version__}")


@check("8. bundled PyPSA-Eur inputs are in place")
def _():
    need = {
        "resources/faisal-2023/regions_offshore_base_s_30.geojson": "offshore regions",
        "resources/faisal-2023/networks/base_s_30_elec_.nc": "prepared network",
        "data/gebco/archive/2014/GEBCO_2014_2D.nc": "depth grid",
    }
    home = Path.home() / "pypsa-eur"
    absent = [w for rel, w in need.items() if not (home / rel).exists()]
    assert not absent, (f"{', '.join(absent)} not found under ~/pypsa-eur. "
                        f"Run: python tools/setup_pypsa_inputs.py")
    return "all three present under ~/pypsa-eur"


# ------------------------------------------------------------- system model

@check("9. PyPSA stack (only needed to re-solve scenarios)")
def _():
    import pypsa
    return f"pypsa {pypsa.__version__}"


print(f"\nRepository: {ROOT}\n")
for status, name, detail in results:
    print(f"[{status}] {name}")
    if detail:
        print(f"         {detail}")

failed = [r for r in results if r[0] == FAIL]
skipped = [r for r in results if r[0] == SKIP]
print(f"\n{len(results) - len(failed) - len(skipped)} passed, "
      f"{len(skipped)} skipped, {len(failed)} failed")
if skipped or failed:
    print("\nWhat you need for what:")
    print("  checks 1-5  the regression model          pip install -r requirements-light.txt")
    print("  checks 6-8  the figures and maps          mamba env create -f environment.yml")
    print("                                            python tools/setup_pypsa_inputs.py")
    print("  check  9    re-solving the system model   see README.md, needs Gurobi")
if failed:
    print("\nSee the Troubleshooting notes in README.md.")
sys.exit(1 if failed else 0)
