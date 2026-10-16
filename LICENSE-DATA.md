# Data, results and documents: licence and attribution

Source code in this repository is under the MIT licence (see `LICENSE`).

Everything else, meaning the data files, derived result tables, figures, the
thesis, the poster and the slide decks, is released under
**[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)**
(CC BY 4.0). You may share and adapt the material, including commercially,
provided you give credit.

**How to credit this work**

> Bindakhil, F. (2026). *Modelling Wind Energy Potentials and Energy Pricing
> Between the North and Baltic Seas.* MSc thesis, Energy Futures Lab, Imperial
> College London.

## Upstream data sources and their own terms

The derived files here are built from public sources. Each keeps its own
licence, and re-use of the derived files does not override those terms. Check
the original source if you plan to redistribute raw data.

| Source | What it provides here | Terms |
|---|---|---|
| **ENTSO-E Transparency Platform** | Day-ahead prices, load, generation by type, cross-border physical flows and commercial exchanges, 2017 to 2024, for 14 countries (`2_Regression_Model/data/entsoe_strandA/`) | Re-use permitted with attribution under the Platform's terms of use. A free account is required to pull fresh data. |
| **ERA5 reanalysis** (ECMWF / Copernicus), accessed through the **Open-Meteo** archive API | Hourly wind speeds at the 31 farm locations, used to build the virtual wind farm output (`2_Regression_Model/data/vwf/`) | Copernicus Licence; Open-Meteo data is CC BY 4.0. Attribute ECMWF and Copernicus. |
| **ENTSO-E / ENTSOG TYNDP 2024** Scenarios Report | Installed capacity trajectories for 2030 and 2040 under National Trends, Distributed Energy and Global Ambition (`2_Regression_Model/data/tyndp/`, `1_PyPSA_Model/configs/`) | Public ENTSO-E scenario data, attribution requested. |
| **PyPSA-Eur** (Technical University of Berlin and contributors) | The European power-system model that Track 1 configures and solves | Model code MIT; bundled data under various open licences documented upstream. **Not vendored here**, you clone it separately. |
| **Danish Energy Agency** technology catalogue, as shipped in PyPSA-Eur | Offshore wind cost and learning trajectories used in the cost field and LCOE | Open, attribution requested. |
| **Global Wind Atlas 4** (DTU / World Bank) | 250 m capacity-factor rasters mosaicked to the roughly 2 km sea field used for the cost and value maps | CC BY 4.0. Attribute the Global Wind Atlas. |
| **GEBCO 2014** grid | Sea-floor depth driving the water-depth term in the cost model | Free to use with attribution to GEBCO. **Not vendored here**, obtained through the PyPSA-Eur data bundle. |
| **NREL** reference turbines (Gaertner et al. 2020, IEA 15 MW) | The power curve converting wind speed to output | Public, cite the technical report. |

## Material deliberately excluded from this repository

Three things were left out on purpose, so do not expect to find them:

1. **Aurora Energy Research, France Power and Renewables Market Forecast
   (October 2025).** A confidential commercial report. It is used in the thesis
   only as an external benchmark, and the three published capture-value
   discounts quoted from it (offshore about 0.94, onshore about 0.89, solar
   about 0.59) are hardcoded with attribution in
   `7_Thesis_Figures/7.10_make_aurora_benchmark.py`. The report itself is not
   redistributable.
2. **Paul Jacquet's (2024) and Lina Efthymiadou's (2025) MSc theses and their
   model notebooks.** This work builds directly on both and cites them
   throughout, but they are other authors' work and are theirs to share.
   Request them through Imperial's Energy Futures Lab.
3. **Credentials.** The scripts read an ENTSO-E API key from `~/.entsoerc` and
   expect a Gurobi licence at `~/gurobi.lic`. Neither file is in this
   repository, and neither should ever be committed.
