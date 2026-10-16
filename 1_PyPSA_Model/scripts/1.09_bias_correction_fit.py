"""
1.09_bias_correction_fit.py

Replaces the single-point "DK2-2023 bias = -0.16" heuristic used by 1.08 with a
multi-zone bias function fitted on the track-B validation points
(5 zones x 3 years: DE, NL, BE, DK1, DK2 in 2019, 2023 and 2024; NL 2019
excluded as low-confidence -> 14 fit points. 2024 added 2026-06-12; the loop
skips any year whose calibration outputs are absent, so the script still runs
on 2 years if 2024 has not been solved yet).

Logic:
  bias(zone, year) = CV_pypsa - CV_obs  (PyPSA over-statement of CV)
  Bias grows with offshore PENETRATION (offshore energy / zone load) because
  the price-flattening pathology worsens as wind floods the zone.
  Fit a linear model: bias ~ penetration.

Method-integrity fixes (2026-06-11, post-audit):
  1. CONSISTENT AXIS. The fit and its application now both use the MODEL's own
     penetration (PyPSA offshore energy / zone load). The previous version
     fitted on OBSERVED penetration but applied the line to MODEL penetration —
     two quantities that differ by 1.3-2.9x in the validation zones. The
     observed-axis fit is retained as a labelled sensitivity.
  2. CLAMPED EXTRAPOLATION. Predicted bias is evaluated at penetration clamped
     to the fit's validated maximum, and corrected CV is floored at 0 — the
     unclamped linear extrapolation (which produced physically impossible
     negative CVs at up to 302% zone penetration) is retained only as a
     labelled sensitivity column, consistent with the surrogate (1.14).
  3. UNCERTAINTY. The slope's standard error, 95% CI, and leave-one-out range
     are reported, and the prediction CI is propagated into aggregate
     CV_corr_lo / CV_corr_hi bands — the headline is a band, not a point.
  4. STALENESS GUARD. The mtimes of every input network are written next to
     the outputs (fit_metadata.txt) so stale results are detectable; the
     previous published CSVs predated the networks they claimed to summarise.
  5. Aggregate penetration is the TRUE ratio of sums (incl. zero-offshore
     zones), and all energy/price sums are snapshot-weighted.

Output: results/projections_v3/
  baltic_per_zone_bias_fit.csv   per zone x scenario, raw + corrected (+bands)
  baltic_cv_fit_corrected.csv    aggregate Baltic CV per scenario (+bands)
  fit_metadata.txt               fit coefficients, diagnostics, input mtimes
  fig_bias_fit_and_corrected.png
"""
import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "projections_v3"
OUT.mkdir(parents=True, exist_ok=True)

DK_LON_CUT = 11.0
BALTIC = ["PL", "FI", "EE", "LV", "LT"]
OFFSHORE = ["offwind-ac", "offwind-dc", "offwind-float"]
V3 = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3"
SCENARIOS = ["2030-NT-balticBaseline", "2030-NT-balticHigh",
             "2040-NT-balticBaseline", "2040-NT-balticHigh",
             "2040-DE-balticHigh", "2040-GA-balticHigh"]

INPUT_FILES = []   # populated as networks are read; recorded in fit_metadata.txt


def _track(path):
    INPUT_FILES.append(path)
    return path


# ---------------------------------------------------------------------------
# 1. Validation data with BOTH penetration axes (model is the canonical one)
# ---------------------------------------------------------------------------
def zone_load_from_baseline(year):
    """Return zone -> annual load (TWh) from the solved baseline network."""
    p = _track(Path.home() / f"pypsa-eur/results/faisal-{year}/networks/base_s_30_elec_.nc")
    n = pypsa.Network(p)
    ac = n.buses[n.buses.carrier == "AC"]
    loads = n.loads
    p_set = n.loads_t.p_set
    w = n.snapshot_weightings.generators
    out = {}
    zones = {c: list(ac[ac.country == c].index) for c in ["DE", "NL", "BE"]}
    dk = ac[ac.country == "DK"]
    zones["DK1"] = list(dk[dk.x < DK_LON_CUT].index)
    zones["DK2"] = list(dk[dk.x >= DK_LON_CUT].index)
    for label, bus_ids in zones.items():
        load_ids = loads[loads.bus.isin(bus_ids)].index
        cols = load_ids.intersection(p_set.columns)
        if len(cols):
            out[label] = float((p_set[cols].sum(axis=1) * w).sum()) / 1e6  # MWh -> TWh
    return out


def build_validation_table():
    rows = []
    for year in [2019, 2023, 2024]:
        cv_path = ROOT / f"results/calibration_{year}/observed_capture_value_comparison.csv"
        if not cv_path.exists():
            print(f"  missing {cv_path}")
            continue
        cv = pd.read_csv(_track(cv_path)).set_index("zone")
        loads = zone_load_from_baseline(year)
        for zone in cv.index:
            if zone not in loads:
                continue
            load_twh = loads[zone]
            rows.append({
                "zone": zone, "year": year,
                # canonical axis: the model's own penetration (consistent with application)
                "pen_model": cv.at[zone, "energy_pypsa_GWh"] / 1e3 / load_twh if load_twh > 0 else np.nan,
                # sensitivity axis: observed penetration (the old, inconsistent choice)
                "pen_obs": cv.at[zone, "energy_obs_GWh"] / 1e3 / load_twh if load_twh > 0 else np.nan,
                "CV_obs": cv.at[zone, "CV_obs"],
                "CV_pypsa": cv.at[zone, "CV_pypsa"],
                "bias": cv.at[zone, "CV_pypsa"] - cv.at[zone, "CV_obs"],
            })
    return pd.DataFrame(rows)


print("=" * 80)
print("1. Validation data with model + observed penetration axes")
print("=" * 80)
val = build_validation_table()
print(val.round(3).to_string(index=False))

# Flag NL 2019 (known thin/under-reported ENTSO-E offshore data)
val["high_confidence"] = ~((val.zone == "NL") & (val.year == 2019))
print(f"\nNL 2019 flagged low-confidence (ENTSO-E under-reported NL offshore pre-2020);"
      f"\nfit uses the remaining {int(val.high_confidence.sum())} of {len(val)} points.")


# ---------------------------------------------------------------------------
# 2. Fit bias ~ penetration with diagnostics (canonical: model axis)
# ---------------------------------------------------------------------------
def ols_with_diagnostics(x, y):
    """Simple OLS y = a + b x with R2, SE(b), 95% CI, and prediction-CI helper."""
    n = len(x)
    A = np.vstack([np.ones_like(x), x]).T
    (a, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    y_hat = a + b * x
    resid = y - y_hat
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    dof = n - 2
    s2 = ss_res / dof
    sxx = float(((x - x.mean()) ** 2).sum())
    se_b = np.sqrt(s2 / sxx)
    se_a = np.sqrt(s2 * (1 / n + x.mean() ** 2 / sxx))
    tcrit = stats.t.ppf(0.975, dof)

    def pred_ci(x0):
        """95% CI half-width of the MEAN prediction at x0."""
        return tcrit * np.sqrt(s2 * (1 / n + (x0 - x.mean()) ** 2 / sxx))

    return dict(a=a, b=b, r2=r2, rmse=np.sqrt(ss_res / n), n=n,
                se_a=se_a, se_b=se_b, tcrit=tcrit,
                b_lo=b - tcrit * se_b, b_hi=b + tcrit * se_b, pred_ci=pred_ci)


print("\n" + "=" * 80)
print("2. Fit: bias = a + b * penetration (canonical axis: MODEL penetration)")
print("=" * 80)
fit_data = val[val.high_confidence].copy()

fit = ols_with_diagnostics(fit_data.pen_model.values, fit_data.bias.values)
PEN_VALID_MAX = float(fit_data.pen_model.max())
print(f"  bias = {fit['a']:+.3f} + {fit['b']:+.3f} * pen_model")
print(f"  R^2 = {fit['r2']:.3f}, RMSE = {fit['rmse']:.3f}, n = {fit['n']}")
print(f"  slope 95% CI [{fit['b_lo']:.3f}, {fit['b_hi']:.3f}]  (SE {fit['se_b']:.3f})")
print(f"  validated penetration range: 0 - {PEN_VALID_MAX:.3f}  (predictions clamped here)")

# leave-one-out slope range (the fit leans on few points; quantify that)
loo = []
for i in range(len(fit_data)):
    sub = fit_data.drop(fit_data.index[i])
    f_i = ols_with_diagnostics(sub.pen_model.values, sub.bias.values)
    loo.append((fit_data.iloc[i].zone, fit_data.iloc[i].year, f_i["b"], f_i["r2"]))
loo_df = pd.DataFrame(loo, columns=["dropped_zone", "dropped_year", "slope", "r2"])
print(f"  leave-one-out slope range: [{loo_df.slope.min():.3f}, {loo_df.slope.max():.3f}]"
      f"  (most influential: {loo_df.loc[(loo_df.slope - fit['b']).abs().idxmax(), 'dropped_zone']}"
      f" {loo_df.loc[(loo_df.slope - fit['b']).abs().idxmax(), 'dropped_year']})")

# sensitivity: the old observed-axis fit, reported for transparency
fit_obs = ols_with_diagnostics(fit_data.pen_obs.values, fit_data.bias.values)
print(f"\n  Sensitivity (OBSERVED-pen axis, the pre-fix choice): "
      f"bias = {fit_obs['a']:+.3f} + {fit_obs['b']:+.3f} * pen_obs, R^2 = {fit_obs['r2']:.3f}")
print("  -> reported only as sensitivity; it is NOT applied to model penetrations.")


# ---------------------------------------------------------------------------
# 3. Apply fit to v3 Baltic projections (clamped, floored, with CI bands)
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("3. Apply bias fit to v3 Baltic projections")
print("=" * 80)


def zone_offshore_data(n, zone):
    ac = n.buses[n.buses.carrier == "AC"]
    buses = list(ac[ac.country == zone].index)
    pr = n.buses_t.marginal_price
    g = n.generators
    w = n.snapshot_weightings.generators
    loads = n.loads[n.loads.bus.isin(buses)]
    lcols = loads.index.intersection(n.loads_t.p_set.columns)
    load_e = float((n.loads_t.p_set[lcols].sum(axis=1) * w).sum()) if len(lcols) else np.nan
    ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(OFFSHORE))].index
           if i in n.generators_t.p.columns]
    if not ids:
        return dict(energy_GWh=0.0, load_GWh=load_e / 1e3 if load_e == load_e else np.nan,
                    CV_raw=np.nan, penetration=np.nan)
    P = n.generators_t.p[ids].sum(axis=1)
    energy = float((P * w).sum())
    if energy <= 0:
        return dict(energy_GWh=0.0, load_GWh=load_e / 1e3 if load_e == load_e else np.nan,
                    CV_raw=np.nan, penetration=np.nan)
    num = pd.Series(0.0, index=P.index)
    for gid in ids:
        bus = g.at[gid, "bus"]
        if bus in pr.columns:
            num += n.generators_t.p[gid] * pr[bus]
    capture = float((num * w).sum()) / energy
    pbuses = [b for b in buses if b in pr.columns]
    base = float((pr[pbuses].mean(axis=1) * w).sum() / w.sum())
    return dict(energy_GWh=energy / 1e3, load_GWh=load_e / 1e3,
                CV_raw=capture / base,
                penetration=energy / load_e if load_e and load_e > 0 else np.nan)


rows = []
for sc in SCENARIOS:
    f = V3 / f"{sc}.nc"
    if not f.exists():
        print(f"  WARNING: missing scenario network {f.name}")
        continue
    n = pypsa.Network(_track(f))
    for zone in BALTIC:
        d = zone_offshore_data(n, zone)
        pen = d["penetration"]
        if d["energy_GWh"] <= 0 or pen != pen:
            d.update(scenario=sc, zone=zone, pen_clamped=np.nan, bias_predicted=np.nan,
                     bias_ci=np.nan, CV_corr_fit=np.nan, CV_corr_lo=np.nan,
                     CV_corr_hi=np.nan, CV_corr_unclamped=np.nan, CV_corr_DK2=np.nan)
            rows.append(d)
            continue
        pen_c = min(pen, PEN_VALID_MAX)            # clamp to validated range
        bias_c = fit["a"] + fit["b"] * pen_c
        ci = fit["pred_ci"](pen_c)
        bias_unc = fit["a"] + fit["b"] * pen        # unclamped (sensitivity only)
        d.update(scenario=sc, zone=zone,
                 pen_clamped=pen_c,
                 bias_predicted=bias_c,
                 bias_ci=ci,
                 CV_corr_fit=max(d["CV_raw"] - bias_c, 0.0),
                 CV_corr_lo=max(d["CV_raw"] - (bias_c + ci), 0.0),
                 CV_corr_hi=max(d["CV_raw"] - (bias_c - ci), 0.0),
                 CV_corr_unclamped=d["CV_raw"] - bias_unc,   # may be < 0; labelled sensitivity
                 CV_corr_DK2=d["CV_raw"] - 0.16)             # old constant heuristic
        rows.append(d)

per_zone = pd.DataFrame(rows)
print("\nPer-zone v3 Baltic CVs (clamped fit, with 95% CI):")
print(per_zone[["scenario", "zone", "penetration", "pen_clamped", "CV_raw",
                "bias_predicted", "CV_corr_fit", "CV_corr_lo", "CV_corr_hi",
                "CV_corr_unclamped"]].round(3).to_string(index=False))
n_clamped = int((per_zone.penetration > PEN_VALID_MAX).sum())
print(f"\n  {n_clamped} zone-scenario rows exceeded the validated penetration range "
      f"(clamped at {PEN_VALID_MAX:.2f}); unclamped values kept as labelled sensitivity.")
per_zone.to_csv(OUT / "baltic_per_zone_bias_fit.csv", index=False)


# ---------------------------------------------------------------------------
# 4. Aggregate Baltic CV (energy-weighted CV, TRUE aggregate penetration)
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("4. Aggregate Baltic CV per scenario (energy-weighted, with CI band)")
print("=" * 80)
agg_rows = []
for sc in SCENARIOS:
    sub_all = per_zone[per_zone.scenario == sc]
    # Finland is set aside from every Baltic aggregate (nuclear-driven outlier,
    # same convention as the maps, deck, and decomposition). Per-zone rows keep FI.
    sub_all = sub_all[sub_all.zone != "FI"]
    sub = sub_all.dropna(subset=["CV_raw", "CV_corr_fit"])
    sub = sub[sub.energy_GWh > 0]
    if sub.empty:
        continue
    w = sub.energy_GWh
    total_load = sub_all.load_GWh.sum()   # ALL Baltic zones, incl. zero-offshore
    agg_rows.append(dict(
        scenario=sc,
        agg_penetration=sub.energy_GWh.sum() / total_load if total_load > 0 else np.nan,
        CV_raw=(sub.CV_raw * w).sum() / w.sum(),
        CV_corr_fit=(sub.CV_corr_fit * w).sum() / w.sum(),
        CV_corr_lo=(sub.CV_corr_lo * w).sum() / w.sum(),
        CV_corr_hi=(sub.CV_corr_hi * w).sum() / w.sum(),
        CV_corr_unclamped=(sub.CV_corr_unclamped * w).sum() / w.sum(),
        CV_corr_DK2_simple=(sub.CV_corr_DK2 * w).sum() / w.sum(),
    ))
agg = pd.DataFrame(agg_rows).set_index("scenario")
# keep the column name 3.01 reads (avg_penetration) pointing at the TRUE aggregate
agg.insert(0, "avg_penetration", agg.pop("agg_penetration"))
print(agg.round(3).to_string())
agg.to_csv(OUT / "baltic_cv_fit_corrected.csv")


# ---------------------------------------------------------------------------
# 5. Metadata (staleness guard) + plot
# ---------------------------------------------------------------------------
meta_lines = [
    f"generated: {datetime.datetime.now().isoformat(timespec='seconds')}",
    f"fit (canonical, MODEL-pen axis): bias = {fit['a']:+.4f} + {fit['b']:+.4f} * pen",
    f"  R2 = {fit['r2']:.4f}, RMSE = {fit['rmse']:.4f}, n = {fit['n']} (NL 2019 excluded)",
    f"  slope 95% CI [{fit['b_lo']:.4f}, {fit['b_hi']:.4f}]",
    f"  leave-one-out slope range [{loo_df.slope.min():.4f}, {loo_df.slope.max():.4f}]",
    f"  penetration clamp: {PEN_VALID_MAX:.4f}; corrected CV floored at 0",
    f"sensitivity fit (OBSERVED-pen axis): bias = {fit_obs['a']:+.4f} + {fit_obs['b']:+.4f} * pen,"
    f" R2 = {fit_obs['r2']:.4f}",
    "",
    "input files (mtime):",
]
for p in INPUT_FILES:
    ts = datetime.datetime.fromtimestamp(Path(p).stat().st_mtime).isoformat(timespec="seconds")
    meta_lines.append(f"  {ts}  {p}")
(OUT / "fit_metadata.txt").write_text("\n".join(meta_lines))
print(f"\nWrote fit metadata + input mtimes -> {OUT / 'fit_metadata.txt'}")

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Left: validation scatter + fit line with CI band
ax = axes[0]
hi = val[val.high_confidence]
lo = val[~val.high_confidence]
ax.scatter(hi.pen_model, hi.bias, s=80, c="steelblue", label="validation points")
ax.scatter(lo.pen_model, lo.bias, s=80, c="lightgray", marker="x",
           label="NL 2019 (excluded)")
# Repel labels so the DK2 anchor points (which the caption directs the reader to)
# are never overprinted -- the fixed-offset version collided DK2 2023/2024.
from adjustText import adjust_text
_texts = [ax.text(r.pen_model, r.bias, f"{r.zone} {r.year}", fontsize=8)
          for _, r in val.iterrows()]
adjust_text(_texts, ax=ax, expand=(1.4, 1.8),
            arrowprops=dict(arrowstyle="-", color="0.6", lw=0.5))
xs = np.linspace(0, PEN_VALID_MAX * 1.1, 100)
ax.plot(xs, fit["a"] + fit["b"] * xs, "k--",
        label=f"fit: bias={fit['a']:+.2f}{fit['b']:+.2f}*pen, R²={fit['r2']:.2f}")
ci_band = np.array([fit["pred_ci"](x0) for x0 in xs])
ax.fill_between(xs, fit["a"] + fit["b"] * xs - ci_band, fit["a"] + fit["b"] * xs + ci_band,
                color="k", alpha=0.12, label="95% CI (mean prediction)")
ax.axvline(PEN_VALID_MAX, color="indianred", lw=1, ls=":",
           label=f"clamp at highest validated penetration ({PEN_VALID_MAX:.2f})")
ax.axhline(0, color="k", lw=0.5)
ax.set_xlabel("Offshore penetration (modelled energy / zone load)")
ax.set_ylabel("Bias = modelled minus observed capture value")
ax.set_title("Model error against modelled offshore penetration", color="#111")
ax.legend(fontsize=8); ax.grid(alpha=0.3)

# Right: corrected aggregate Baltic CV with CI whiskers
ax = axes[1]
x = np.arange(len(agg))
ax.bar(x - 0.25, agg.CV_raw, 0.25, label="raw", color="steelblue")
ax.bar(x, agg.CV_corr_fit, 0.25, label="fit-corrected (clamped)", color="seagreen")
ax.errorbar(x, agg.CV_corr_fit,
            yerr=[(agg.CV_corr_fit - agg.CV_corr_lo).clip(lower=0),
                  (agg.CV_corr_hi - agg.CV_corr_fit).clip(lower=0)],
            fmt="none", ecolor="k", capsize=3, lw=1)
ax.bar(x + 0.25, agg.CV_corr_DK2_simple, 0.25, label="constant DK2 offset", color="indianred")
ax.set_xticks(x); ax.set_xticklabels(agg.index, rotation=20, fontsize=8, ha="right")
ax.set_ylabel("Aggregate Baltic CV"); ax.axhline(1.0, color="k", ls="--", lw=0.5)
ax.set_title("Baltic capture value, raw and corrected", color="#111")
ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(OUT / "fig_bias_fit_and_corrected.png", dpi=130)
plt.close()
print(f"Saved -> {OUT / 'fig_bias_fit_and_corrected.png'}")
