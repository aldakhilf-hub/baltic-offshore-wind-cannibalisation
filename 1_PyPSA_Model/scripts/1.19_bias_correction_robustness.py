"""
1.19_bias_correction_robustness.py  ·  TRACK 1 — robustness of the bias correction

The 1.09 bias fit (bias ~ model penetration) is fitted on 14 validation points
(5 zones x 3 years, NL 2019 excluded). This script tests how much of it rests on
DK2, the only validation zone above ~31% offshore penetration, by refitting under
leave-one-ZONE-out (drop ALL years of a zone) and leave-one-YEAR-out, and by
re-applying each variant to the Baltic projection to show the headline impact.

Finding (the appendix figure): the penetration slope is anchored entirely on DK2.
Dropping DK2 collapses the slope from 0.233 to 0.045 and its 95% CI crosses zero
(R2 0.47 -> 0.02); dropping any other zone barely moves it. The CORRECTION is
therefore a DK2-anchored refinement, not a robust law — but the CONCLUSION
survives, because the raw engine already produces 0.46-0.57 in 2040 and the
DK2-out correction lands at 0.41-0.53.

Outputs -> results/projections_v3/:
  bias_correction_robustness.csv   leave-one-zone-out + leave-one-year-out fits
  bias_projection_under_lozo.csv   corrected 2040 Baltic CV under each fit variant
  fig_bias_lozo.png                the 14 points with the canonical vs DK2-out line

Usage:  python 1.19_bias_correction_robustness.py   (env pypsa-eur-arm64)
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "projections_v3"
OUT.mkdir(parents=True, exist_ok=True)
DK_LON_CUT = 11.0
PERZONE = pd.read_csv(OUT / "baltic_per_zone_bias_fit.csv")
SCEN2040 = ["2040-NT-balticBaseline", "2040-NT-balticHigh", "2040-DE-balticHigh", "2040-GA-balticHigh"]


def zone_load_twh(year):
    n = pypsa.Network(Path.home() / f"pypsa-eur/results/faisal-{year}/networks/base_s_30_elec_.nc")
    ac = n.buses[n.buses.carrier == "AC"]
    loads, p_set, w = n.loads, n.loads_t.p_set, n.snapshot_weightings.generators
    out, zones = {}, {c: list(ac[ac.country == c].index) for c in ["DE", "NL", "BE"]}
    dk = ac[ac.country == "DK"]
    zones["DK1"] = list(dk[dk.x < DK_LON_CUT].index)
    zones["DK2"] = list(dk[dk.x >= DK_LON_CUT].index)
    for label, bus_ids in zones.items():
        cols = loads[loads.bus.isin(bus_ids)].index.intersection(p_set.columns)
        if len(cols):
            out[label] = float((p_set[cols].sum(axis=1) * w).sum()) / 1e6
    return out


def build_points():
    rows = []
    for year in [2019, 2023, 2024]:
        cv = pd.read_csv(ROOT / f"results/calibration_{year}/observed_capture_value_comparison.csv").set_index("zone")
        loads = zone_load_twh(year)
        for z in cv.index:
            if z in loads:
                rows.append(dict(zone=z, year=year,
                                 pen=cv.at[z, "energy_pypsa_GWh"] / 1e3 / loads[z],
                                 bias=cv.at[z, "CV_pypsa"] - cv.at[z, "CV_obs"]))
    df = pd.DataFrame(rows)
    return df[~((df.zone == "NL") & (df.year == 2019))].copy()   # NL 2019 excluded


def ols(x, y):
    n = len(x)
    A = np.vstack([np.ones_like(x), x]).T
    (a, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    yh = a + b * x
    ss_res, ss_tot = float(((y - yh) ** 2).sum()), float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    s2 = ss_res / (n - 2)
    sxx = float(((x - x.mean()) ** 2).sum())
    se_b = np.sqrt(s2 / sxx)
    t = stats.t.ppf(0.975, n - 2)
    return dict(a=a, b=b, r2=r2, n=n, b_lo=b - t * se_b, b_hi=b + t * se_b, pen_max=float(x.max()))


def corrected_2040(a, b, clamp):
    out = {}
    for sc, g in PERZONE.groupby("scenario"):
        g = g[g.zone != "FI"]   # Finland set aside from the aggregate, matching 1.09
        g = g.dropna(subset=["CV_raw", "penetration", "energy_GWh"])
        g = g[g.energy_GWh > 0]
        if g.empty:
            continue
        cv = (g.CV_raw - (a + b * g.penetration.clip(upper=clamp))).clip(lower=0)
        out[sc] = (cv * g.energy_GWh).sum() / g.energy_GWh.sum()
    return out


df = build_points()
full = ols(df.pen.values, df.bias.values)
print(f"Canonical (n={full['n']}): bias = {full['a']:+.4f} + {full['b']:.4f}*pen | "
      f"R2={full['r2']:.3f} | slope CI [{full['b_lo']:.3f}, {full['b_hi']:.3f}]")

rows = []
for kind, key in [("zone", "zone"), ("year", "year")]:
    for v in sorted(df[key].unique()):
        f = ols(df[df[key] != v].pen.values, df[df[key] != v].bias.values)
        rows.append(dict(drop_kind=f"leave-one-{kind}-out", dropped=v, n=f["n"],
                         slope=round(f["b"], 4), ci_lo=round(f["b_lo"], 4), ci_hi=round(f["b_hi"], 4),
                         excludes_zero=(f["b_lo"] > 0 or f["b_hi"] < 0), r2=round(f["r2"], 4),
                         pen_max=round(f["pen_max"], 4)))
rob = pd.DataFrame(rows)
rob.to_csv(OUT / "bias_correction_robustness.csv", index=False)
print("\n" + rob.to_string(index=False))

# headline impact: corrected 2040 under raw / canonical / drop-DK2
proj = [dict(fit="raw (no correction)", **{s: round(v, 3) for s, v in corrected_2040(0, 0, 1.0).items()})]
for label, sub in [("canonical (14)", df), ("drop DK2", df[df.zone != "DK2"])]:
    f = ols(sub.pen.values, sub.bias.values)
    proj.append(dict(fit=label, **{s: round(v, 3) for s, v in corrected_2040(f["a"], f["b"], f["pen_max"]).items()}))
projdf = pd.DataFrame(proj)
projdf.to_csv(OUT / "bias_projection_under_lozo.csv", index=False)
print("\nCorrected 2040 Baltic CV per fit variant:")
print(projdf[["fit"] + SCEN2040].to_string(index=False))

# ---- figure: the 14 points with the canonical vs DK2-dropped fit line ----
dk2_fit = ols(df[df.zone != "DK2"].pen.values, df[df.zone != "DK2"].bias.values)
fig, ax = plt.subplots(figsize=(8, 5))
colors = {"DE": "#2471a3", "NL": "#7fb3d5", "BE": "#16a085", "DK1": "#e67e22", "DK2": "#c0392b"}
for z, g in df.groupby("zone"):
    ax.scatter(g.pen, g.bias, s=90, color=colors.get(z, "grey"),
               edgecolor="k" if z == "DK2" else "white", lw=1.2, zorder=3,
               label=z + (" (anchors the slope)" if z == "DK2" else ""))
xs = np.linspace(0, full["pen_max"] * 1.05, 100)
ax.plot(xs, full["a"] + full["b"] * xs, "k-", lw=2,
        label=f"canonical fit  (b={full['b']:.2f}, R²={full['r2']:.2f})")
ax.plot(xs, dk2_fit["a"] + dk2_fit["b"] * xs, "k--", lw=1.6,
        label=f"DK2 dropped  (b={dk2_fit['b']:.2f}, R²={dk2_fit['r2']:.2f}, CI crosses 0)")
ax.axhline(0, color="grey", lw=0.6)
ax.axvline(full["pen_max"], color="indianred", ls=":", lw=1,
           label=f"clamp = DK2 penetration ({full['pen_max']:.2f})")
ax.set(xlabel="Offshore penetration (model energy / zone load)",
       ylabel="Bias = CV$_{\\mathrm{PyPSA}}$ − CV$_{\\mathrm{obs}}$",
       title="The bias-correction slope is anchored on a single zone (DK2)\n"
             "Drop DK2 and the penetration dependence vanishes (R² 0.47 → 0.02)")
ax.legend(fontsize=8, loc="upper left"); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / "fig_bias_lozo.png", dpi=150)
print(f"\nSaved -> {OUT}/bias_correction_robustness.csv, bias_projection_under_lozo.csv, fig_bias_lozo.png")
