#!/usr/bin/env python3
"""Put the bundled PyPSA-Eur input files where the analysis scripts look for them.

    python tools/setup_pypsa_inputs.py

Around twenty scripts in 7_Thesis_Figures and 2_Regression_Model need three
files that normally come out of a PyPSA-Eur build: the offshore region polygons
for the 30-cluster model, the prepared (unsolved) network, and the GEBCO depth
grid. Building those yourself means installing PyPSA-Eur and running its
snakemake chain, where the weather cutout alone takes over four hours.

All three are small, so they ship in this repository under pypsa_inputs/. This
script copies them to ~/pypsa-eur, which is where the scripts expect them. You
do not need PyPSA-Eur installed for this to work, and if you install it later
the directories simply merge.

Nothing is overwritten unless you pass --force. Pass --link to symlink instead
of copy, which saves 46MB.
"""
from pathlib import Path
import argparse
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "pypsa_inputs"
DEST = Path.home() / "pypsa-eur"

WHAT_FOR = {
    "resources/faisal-2023/regions_offshore_base_s_30.geojson":
        "offshore region polygons, needed by every map and heatmap script",
    "resources/faisal-2023/networks/base_s_30_elec_.nc":
        "prepared unsolved network, needed by the analytical and SHAP scripts",
    "data/gebco/archive/2014/GEBCO_2014_2D.nc":
        "sea-floor depth, needed by the cost field, LCOE and site ranking",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="overwrite files already present at the destination")
    ap.add_argument("--link", action="store_true",
                    help="create symlinks instead of copying")
    args = ap.parse_args()

    if not SRC.exists():
        print(f"ERROR: {SRC} is missing. Re-clone the repository.")
        return 1

    print(f"source:      {SRC}")
    print(f"destination: {DEST}\n")

    copied = skipped = failed = 0
    for rel, why in WHAT_FOR.items():
        src, dst = SRC / rel, DEST / rel
        print(f"  {rel}")
        print(f"    {why}")

        if not src.exists():
            print("    MISSING from the repository, skipping\n")
            failed += 1
            continue
        if dst.exists() and not args.force:
            print("    already present, leaving it alone (use --force to replace)\n")
            skipped += 1
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        if args.link:
            dst.symlink_to(src.resolve())
            print("    linked\n")
        else:
            shutil.copy2(src, dst)
            print(f"    copied, {dst.stat().st_size / 1e6:.0f}MB\n")
        copied += 1

    verb = "linked" if args.link else "copied"
    print(f"{copied} {verb}, {skipped} already present, {failed} missing")
    if failed:
        return 1
    print("\nThe map and figure scripts in 7_Thesis_Figures should now run. "
          "Re-solving scenarios still needs a real PyPSA-Eur install and Gurobi; "
          "see README.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
