# Two estimators of one quantity: theory, predictions, and what the runs actually did

Prepared for the supervisor's question: *the thesis carries a statistical model and a
system model of the same number. Why should they differ, mathematically rather than
rhetorically, and do the observed differences match that theory?*

Everything below is tested in `3.02_theory_vs_evidence.py`; tables in
`results/03_theory_vs_evidence/`, figure `fig_theory_vs_evidence.png`.

---

## 1. The two estimators, stated properly

Both estimate the same object, the generation-weighted capture value of a farm

$$CV \;=\; \frac{\sum_t g_t\,p_t}{\left(\sum_t g_t\right)\bar p}$$

but they obtain the price $p_t$ by routes that share no assumption.

**Estimator A, the regression.** A gradient-boosted ensemble

$$\widehat{CV}(x) \;=\; \sum_{k=1}^{400} f_k(x), \qquad x\in\mathbb R^{7}$$

where each $f_k$ is a depth-limited regression tree: a piecewise-constant function on a
partition of feature space induced by splits chosen from the training rows. Three
properties follow directly and matter enormously.

1. **Boundedness.** Every leaf value is a function of training targets, so the ensemble's
   output cannot leave the range of observed capture values. It can never predict a
   collapse it has never seen.
2. **Local constancy.** $\partial \widehat{CV}/\partial x = 0$ almost everywhere, since the
   prediction is constant within each leaf. The model has no gradient in the usual sense.
3. **No splits beyond the data.** Splits exist only where training rows exist. Outside the
   training hull the enclosing leaf is unbounded, so the prediction is *exactly constant*
   in the direction of extrapolation.

**Estimator B, PyPSA.** A cost-minimising dispatch and investment program

$$\min_x c^\top x \quad \text{s.t.} \quad Ax \le b,\; x \ge 0$$

in which the price is not fitted at all: it is the dual variable $\lambda_{n,t}$ of the
nodal energy-balance constraint. By complementary slackness $\lambda_{n,t}$ equals the
marginal cost of the marginal unit at that node and hour. Its properties are the mirror
image of A's.

1. **No training range.** The program re-solves for any input, however unprecedented.
2. **Structural response.** Changing the fleet changes the merit order, so the price
   responds through physics rather than through a fitted association.
3. **Bounded below at zero.** With non-negative marginal costs and no negative bidding, an
   LP cannot produce negative prices. This will matter in section 4.

**The deepest difference is in where the error lives.** The regression is close to
unbiased where data is dense, and its error is variance: finite sample, finite farms.
PyPSA has no sampling error at all, and its error is bias: perfect foresight,
copper-plate clusters, no unit commitment, inelastic demand. Two estimators, two
error types. That single sentence organises everything that follows.

---

## 2. Five predictions

| | Prediction | Follows from |
|---|---|---|
| **P1** | Every 2030/2040 scenario leaves the training envelope | the projection is a different world, not a bigger sample |
| **P2** | The tree's prediction is near-invariant to scenario severity; PyPSA's is not | A2, A3 vs B1, B2 |
| **P3** | The loss is convex in penetration, and the linear analytical form cannot represent it | merit-order theory (Hirth); the fitted form is linear in VRE share by construction |
| **P4** | The two agree where data is dense and diverge with penetration | A is unbiased in support; only B moves outside it |
| **P5** | PyPSA's in-sample error is positive and largest in small, hydro-coupled, well-connected zones | all three of its approximations push capture value up, and compound exactly there |

---

## 3. What the runs did

**P1 confirmed, and more strongly than expected.** Zero of thirty-six projection rows sit
inside the seven-dimensional training hull; zero sit inside even the looser per-feature
box. Carbon runs 65% beyond the training span by 2040 and VRE share runs 906% beyond it.
Gas and flexibility stay inside their historical ranges, so the excursion is specifically
in the two variables that drive cannibalisation. The regression is formally extrapolating
in every future scenario it is asked about.

**P2 confirmed, decisively.** Across the four Baltic scenarios, from mild 2030 to severe
2040:

| Estimator | Range of predicted CV | Relative to the tree |
|---|---|---|
| XGBoost (tree) | **0.008** | 1× |
| Linear (OLS) | 0.102 | 13× |
| Analytical closed form | 0.179 | 22× |
| PyPSA (LP dual) | **0.461** | **58×** |

The tree moves eight thousandths of a capture value across scenarios that PyPSA separates
by nearly half. This is not a modelling choice, it is property A1 and A3 made visible: the
tree is answering from inside a range that does not contain the answer.

**P4 confirmed.** Where both can be checked against observation (2023-24), they agree:
mean absolute divergence 0.062, with the blind regression within 0.012 of observed. The
divergence then grows to 0.028 at 2030 and 0.320 at 2040, an eleven-fold widening between
horizons and five-fold relative to the region where reality can arbitrate. Agreement
exactly where the data lives, divergence exactly where it does not, is the signature the
theory demands.

**P5 confirmed, including the ordering.** PyPSA's mean signed in-sample error is **+0.056**,
positive as predicted, while the regression's is **−0.004**. The zone ordering is what the
mechanism predicts:

| Zone | PyPSA error | Regression | Structure |
|---|---|---|---|
| DK2 | **+0.142** | +0.004 | small, hydro-coupled to SE/NO |
| DK1 | +0.083 | −0.002 | small, hydro-coupled |
| BE | +0.031 | −0.007 | small, not hydro-coupled |
| DE | +0.015 | −0.005 | large |
| NL | +0.010 | −0.008 | medium |

Perfect-foresight hydro floors the Nordic price, the copper-plate tie to Sweden stops the
local price collapsing, and the LP cannot produce the negative-price tail. All three
compound in a small, hydro-adjacent, well-interconnected zone, which is precisely DK2 and
precisely where the error is largest. This is the same conclusion the June 2026
re-dispatch experiments reached by brute force, now derived from the model's structure
rather than discovered by trial.

---

## 4. P3 failed, and the failure is worth more than the prediction

Fitted on the 76-run surrogate experiment with zone fixed effects and controls for gas,
carbon and demand, errors clustered by run:

$$\text{loss} \;=\; 0.947\,\text{pen} \;-\; 0.193\,\text{pen}^2 \;+\;\text{controls}, \qquad R^2 = 0.58$$

The quadratic term is **negative**, with a 95% confidence interval of
$[-0.215, -0.169]$ that excludes zero, and the sign survives restriction to
$\text{pen}<1.0$ and $\text{pen}<0.6$. **PyPSA's cannibalisation loss is concave, not
convex.** The damage is steepest at low penetration and decelerates thereafter.

Two things follow.

**First, the mechanism the thesis currently names is the wrong one.** The divergence at
2040 is not "the convex collapse the linear form cannot represent". Its true causes are
the two the same script measures directly. The tree's partial dependence on VRE share has
slope **−0.020 inside the training support and exactly −0.0000 outside it**: it does not
extrapolate badly, it does not extrapolate at all. And the linear form's fitted slope is
far shallower than the system model's response, because it was estimated over a historical
window in which penetration barely moved and the 2022 fuel shock dominated the variance,
the same confound the demeaned SHAP analysis already found. Support and slope, not
curvature.

**Second, the concavity is itself an artefact, and it makes the headline conservative.**
An LP with non-negative costs floors prices at zero. Once wind has driven the price to
zero in its windy hours, additional wind cannot push it lower, so the marginal damage must
fall away and the loss must saturate. Real markets do go negative, which is why the
literature expects convexity. So PyPSA understates cannibalisation at high penetration,
and the 2040 capture values of 0.57 and 0.47 should be read as **upper bounds**. This is
the same limitation that makes the zero-price exposure in the CfD analysis a conservative
floor, and it points the headline in the safe direction.

---

## 5. What to say

The two instruments differ because one interpolates a bounded function of seven features
and the other re-derives a shadow price from the merit order. That predicts five things.
Four happen: every projection extrapolates, the tree cannot respond to severity, the
models agree where data is dense and part where it is not, and the system model's error
is positive and concentrated exactly where its approximations compound. The fifth,
convexity, does not happen, and testing it produced something better than confirmation:
the real reason for the 2040 divergence is a flat extrapolation rather than a missed
curvature, and the model's own price floor means the headline erosion is conservative.

The division of labour survives intact, and now rests on measured structure rather than
assertion. The regression is the right instrument in-sample, where it is nearly unbiased
and the system model carries a known positive bias. PyPSA is the only instrument
admissible out of sample, because the alternative is provably constant there.

---

## 6. Wording to correct

The claim that the 2040 gap is a convex collapse appears in:

- `9_Thesis_LaTeX/05_discussion.tex` lines 63, 192, 204, 221
- `9_Thesis_LaTeX/06_conclusion.tex` line 51
- deck slide 25 (bullet 3 and speaker notes), slide 9 notes

Each should become the accurate statement: the empirical form cannot extrapolate, its
tree being exactly constant beyond the training hull and its linear variant carrying a
slope fitted where penetration scarcely varied. The literature review's description of
convexity at line 333 of `02_literature.tex` is a claim about real markets and stands;
what changes is only the claim about *this model's* output.
