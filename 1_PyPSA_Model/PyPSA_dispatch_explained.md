# PyPSA dispatch: inputs, process, equations, outputs — and why it differs from the regression

> Companion to `5_BRIEFING_PyPSA_for_supervisor.md` (the plain-language pitch). This
> one is the technical walkthrough: what goes in, the equations the solver actually
> solves, what comes out, and the equation-level reason the system model (PyPSA) and
> the empirical regression give different 2040 answers. Numbers are the current
> central scenario (NT-balticBaseline, 2026-06-22).

---

## 0 · The one-sentence difference

**PyPSA *solves* the electricity market hour by hour from physics and costs; the
regression *fits* a smooth curve to history.** They agree on the recent past (both
anchored on observed prices) and diverge in the high-penetration Baltic future,
because the two things PyPSA has and the regression does not — a transmission grid
and an hourly market-clearing price — are exactly what drive the Baltic's collapse.

---

## 1 · INPUTS — everything that goes into a solve

| Group | What it is | Source |
|---|---|---|
| **A. Grid** | ~30 regional nodes (*buses*) across 14 NS+Baltic countries; AC lines + DC links between them, each with a transfer capacity. **Frozen at the 2020 grid** for the headline (or made expandable for the optimal-grid run). | PyPSA-Eur base network, clustered |
| **B. Fleet / energy mix** | Every generator at every node, by carrier — offshore wind, onshore wind, solar, gas (CCGT/OCGT), coal, lignite, oil, nuclear, hydro, biomass, battery, H2 electrolyser — each with an installed capacity `p_nom`, an efficiency, a CO₂ intensity, and a marginal cost. **This is the energy mix.** | Present: ENTSO-E/PyPSA-Eur. Future: TYNDP 2024 (BEST) + documented corrections (coal phase-out, DK1/DK2 split, PL nuclear, H2 floor) |
| **C. Weather → availability** | Hourly capacity factor for every wind and solar generator, i.e. the *maximum* it can produce each hour. | ERA5 reanalysis → `atlite` → per-node hourly profiles |
| **D. Demand** | Hourly electricity load at every node. | TYNDP demand growth applied to the historical hourly shape |
| **E. Costs** | Fuel prices (gas, coal, lignite, oil) and the CO₂ price. These set each thermal plant's **marginal cost** and therefore the merit order. Plus a load-shedding price cap (4,000 €/MWh) and a demand-response tier (400 €/MWh). | TYNDP fuel/CO₂ sheets |
| **F. Storage** | Battery power/energy, pumped hydro, H2 electrolyser demand. | TYNDP + corrections |

Everything in B, C, D, E, F is **exogenous** (you supply it). The solve decides only
*how to operate* that fleet, not what to build (capacities are fixed in dispatch mode).

---

## 2 · THE PROCESS — what the solver actually solves

PyPSA assembles one big **linear program (LP)** over all 8,760 hours at once and hands
it to Gurobi. In dispatch mode the decision variables are the hourly generation of
every plant, the hourly flow on every line, and the hourly charge/discharge of every
store.

### Objective — minimise total system operating cost

$$\min \sum_{t}\sum_{g} c_g \, p_{g,t}$$

where $p_{g,t}$ is the power of generator $g$ in hour $t$, and $c_g$ is its **marginal
cost**:

$$c_g = \underbrace{\frac{\text{fuel price}}{\eta_g}}_{\text{fuel}} + \underbrace{\frac{\text{CO}_2\text{ price}\times e_g}{\eta_g}}_{\text{carbon}} + \text{VOM}_g$$

For wind and solar $c_g \approx 0$ (no fuel, no emissions). For gas it is high and rises
with the CO₂ price. This single number is what orders the merit curve.

### Subject to four constraint families

**(1) Nodal energy balance** — supply = demand at every node, every hour:

$$\sum_{g\in n} p_{g,t} \;+\; \sum_{\ell \to n} f_{\ell,t} \;-\; \sum_{\ell \leftarrow n} f_{\ell,t} \;+\; (\text{storage}) \;=\; d_{n,t}$$

**The shadow price (Lagrange multiplier) of this constraint, $\lambda_{n,t}$, IS the
wholesale price** at node $n$ in hour $t$. It equals the marginal cost of serving one
more MWh there — i.e. the cost of the *last* (most expensive) unit dispatched to that
node in that hour. This is the single most important line in the whole model.

**(2) Generator limits** — you cannot produce more than the weather allows:

$$0 \le p_{g,t} \le \bar{a}_{g,t}\, \cdot P^{\text{nom}}_g$$

where $\bar a_{g,t}$ is the hourly availability — for wind/solar this is the ERA5
capacity factor (input C), for thermal it is ≈1.

**(3) Transmission limits** — flows cannot exceed line capacity:

$$|f_{\ell,t}| \le F_\ell$$

$F_\ell$ is **fixed at the 2020 grid** in the headline run, or made a decision variable
(with a capital cost) in the optimal-grid run. This single switch is what the grid
bracket tests.

**(4) Storage dynamics** — state of charge evolves and is cyclic over the year:

$$\text{SOC}_{s,t} = \text{SOC}_{s,t-1} + \eta\,p^{\text{charge}}_{s,t} - p^{\text{discharge}}_{s,t}/\eta, \qquad 0 \le \text{SOC}_{s,t} \le E_s$$

Gurobi solves this with a barrier method (no crossover) for solver parity with the
validated baseline. One scenario ≈ 10 minutes.

### Why this produces cannibalisation, mechanically

In a **windy hour**, zero-cost wind is the marginal unit, so $\lambda \to 0$. In a
**still hour**, gas is marginal, so $\lambda$ is high. A wind farm earns $\lambda$ in
exactly the hours it generates — the cheap ones — and misses the expensive still
hours. As penetration rises, the *share* of hours where wind is marginal grows, and in
an enclosed zone with a binding line limit (constraint 3) the local price hits zero
**faster than linearly**. That convex collapse is the whole story, and it falls
straight out of solving (1)–(3) every hour.

---

## 3 · OUTPUTS — what comes back

| Output | Symbol | Used for |
|---|---|---|
| Hourly nodal price | $\lambda_{n,t}$ = `buses_t.marginal_price` | the wholesale price — the key output |
| Hourly generation | $p_{g,t}$ = `generators_t.p` | dispatch, energy by carrier |
| **Capture value** (the thesis quantity) | see below | offshore wind's earned value |
| System cost, CO₂, line flows | — | context, congestion diagnosis |

Capture value for zone $z$ is built directly from the two outputs above:

$$\text{CV}_z = \frac{\sum_t p^{\text{wind}}_{z,t}\,\lambda_{z,t} \big/ \sum_t p^{\text{wind}}_{z,t}}{\frac{1}{T}\sum_t \lambda_{z,t}} = \frac{\text{generation-weighted price}}{\text{time-average price}}$$

This is the **identical formula** used on the observed side and in Paul Jacquet's work —
only the price source changes (observed ENTSO-E vs PyPSA $\lambda$).

---

## 4 · WHY PyPSA AND THE REGRESSION DIVERGE

Both compute the same capture-value formula. They differ in **where the price comes
from**, and that is the entire reason their 2040 answers split.

| | **PyPSA dispatch** | **Regression** |
|---|---|---|
| Nature | physical LP, solves market clearing | statistical fit, CV = f(7 features) |
| Price $\lambda$ | endogenous, from the hourly merit order | never modelled; CV inferred from features |
| The grid | explicit lines + congestion (constraint 3) | **absent** — no transmission term at all |
| Penetration effect | **convex** — windy-hour price collapse accelerates | **linear** — a proportional penalty only |
| Out-of-range future | solves it from physics | tree flat-lines; linear extrapolates smoothly |

The two methods differ on exactly the two things the regression lacks:

1. **The convex price collapse.** Penetration enters the regression's analytical form
   *linearly*, so it can only subtract a straight-line penalty and bottoms out around
   **0.77** (Baltic 2040). PyPSA clears every hour, sees the accelerating share of
   near-zero-price hours, and reaches **0.50**.
2. **The transmission grid.** The Baltic's extra erosion is largely congestion: a
   frozen line limit (constraint 3) that cannot export the correlated surplus. The
   regression has no grid term, so it cannot represent enclosure at all — which is why
   it reports Baltic ≈ North Sea.

The numbers line up with this reading:

| 2040 capture value | North Sea | Baltic | What it isolates |
|---|---|---|---|
| **Regression** (linear) | 0.74 | 0.77 | no grid, no convexity → no enclosure penalty |
| **PyPSA, frozen grid** | 0.57 | 0.50 | convex collapse **+** binding congestion |
| **PyPSA, optimal grid** | 0.64 | 0.68 | convex collapse only (congestion relieved) |

Read down the Baltic column: relax the grid (constraint 3) and PyPSA moves *toward* the
regression's no-penalty world — the Baltic recovers from 0.50 to 0.68. The part that
remains below the regression's 0.77 is the convex collapse the regression can never
see. So the optimal-grid experiment cleanly separates the two sources of divergence:
**congestion** (the 0.50→0.68 jump) and **convexity** (the residual 0.68 vs 0.77).

This is why the thesis uses both instruments. The regression measures the present and
the mechanism where it is anchored on real prices; PyPSA carries the future, because
only a model that solves the grid and the market hour by hour can produce the two
effects that decide the Baltic's fate.
