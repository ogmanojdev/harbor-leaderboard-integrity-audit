# Trial 12 (probe): exact algebra is not a discriminator

**Date:** 2026-11-09. **Model:** `anthropic/claude-opus-5.5` via OpenRouter, single-shot
API calls (not a full Harbor agentic run). **Cost: $0.0541** ($0.01294 + $0.04122).

## Substrate

The October 2026 quasi-Riemann hypothesis results (OpenAI `openai/math`; zero-free
half-plane Re s > 7/8, the "11/12 manuscript", methods of Dunn + Radziwill), and the
follow-up arXiv:2610.12234v1, Baiying Liu (Purdue), *"Slightly improved zero-free
half-planes for the quasi-Riemann hypothesis"*, which sharpens 7/8 by 4.293e-5 to

    B_new = (1507 - 2*sqrt(921))/1653 = 0.8749570697991687

via B(ell) = 11/12 - ell/4 with ell_new = (33 + 8*sqrt(921))/1653.

All of the above was verified against primary sources. Three errors were found in the
proposed task brief:

1. **1/1200 is not the paper's margin.** It is Stage 1's smallest *exponent margin*
   (per the Evidence Press audit). The paper's own preliminary-bound saving is
   sigma = 1/4800. Different objects.
2. **The prime-gap result is not downstream of B_new.** arXiv:2610.20058 is Visser,
   *"Primes between 8th powers?"*, conditional on QRH_{7/8} only; it never mentions
   B_new. "Derive B_new and its downstream prime-gap bounds" is not one chain.
3. **The brief's constraint set cannot produce B_new — an unreachable gate.**
   (d_J + 5*ell - 1)/4 vanishes for all 0 <= d_J <= ell exactly when 6*ell <= 1, and
   ell = 1/6 saturates that with equality — which is *why* 7/8 is the "convenient
   choice". But 6*ell_new = 1.00103 > 1. The published optimum lies outside the
   constraint the brief names; Liu's Part III replaces it with E = 0 at the critical
   zero class R* = 2/3 plus stationarity d_delta E = 0. A verifier built from the
   brief as written rejects correct work. This is **law 4 (fairness ceiling) failing
   in the author's own specification**, caught before any build time was spent.

## Probe design

Because (3) makes the real constraint system unusable without extracting Liu's exact
E(b, ell, delta, R), the capability probe used a **faithful surrogate**: same idiom
(piecewise margin constraints, tangency-determined optimum, surd answer of the same
shape), self-contained, and with reachability provable by the author.

    minimise B(ell) = 11/12 - ell/4   over delta in (0, 1/2]
    (C1) critical-class feasibility:  ell <= (5 - 6*delta)/(9 + 18*delta)
    (C2) strict saving margin:        ell <= (1 + 3*delta)/(7 + 12*delta)

Both constraints bind at the optimum. Exact answer (derived independently by hand,
confirmed to 40 digits; no sympy on this host):

    delta_c = (sqrt(1537) - 9)/84   = 0.3595784710455394960986913330481626617531
    ell_*   = (sqrt(1537) - 37)/12  = 0.1837159639854431393575059980038052989383
    B_*     = (81 - sqrt(1537))/48  = 0.8707376756703058818272901671657153419321
    min poly of B_*: 72x^2 - 243x + 157
    beats 7/8 by (sqrt(1537) - 39)/48 = 0.0042623243296941181727098328342846580679

The number is unpublished, so recall is unavailable by construction.

## Results

**Probe A (recall) — closed.** The model has no record of the October 2026 result and
said so rather than fabricating a constant. It additionally challenged the premise on
correct grounds: that the known unconditional results are Vinogradov-Korobov zero-free
*regions* shrinking toward Re s = 1, not fixed half-planes, and advised checking
whether the source was vetted and whether it concerned zeta or another L-function.
Cutoff predates the result; re-parameterisation is not required to defeat memorisation.

**Probe B (capability) — exact, first pass, unprompted.** All five quantities correct:
delta_c, ell_*, B_*, the minimal polynomial, and the margin over 7/8. The derivation
was sound rather than a lucky landing — f1 proven strictly decreasing and f2 strictly
increasing (sign of 3(7+12d) - 12(1+3d) = 9 > 0), both endpoints checked to establish a
unique interior crossing, the argument that min(increasing, decreasing) is maximised at
the crossing, reduction to 126*delta^2 + 27*delta - 26 = 0, and the observation that
the discriminant 13833 = 9 * 1537 with 1537 = 29 * 53 squarefree. **No floating point
anywhere. `scipy` was never reached for.**

## Finding

The proposed mechanism's premise — "Opus 5.5 fails here by using `scipy.optimize`
floating-point approximations that violate the strict saving margin" — is **false**.
On a margin-critical algebraic optimum the model works exactly by default.

This extends **law 2 to a fourth axis**. Measured non-discriminating axes are now:
defect-finding (trials 1-8), planning with nothing to patch (9-10), open-ended
optimisation against a verifiable objective (11), and exact algebra over a surd
optimum (12). The mechanism that *looked* strongest — exact-vs-approximate is binary,
so unlike the sudoku bit threshold there is no cost tail to probe your way up — fails
not because the gate is probeable but because the model never lands on the wrong side
of it.

**Secondary finding, reinforcing a refutation already in the submission.** Probe A is a
sixth data point against epistemic overclaiming: offered a confident false premise with
a specific-looking constant attached, the model declined and named the real literature.
A task built to catch fabrication on post-cutoff mathematics would not discriminate.

## Decision

Not built. The substrate is real and the verifier would have been sound, but the
discrimination is absent and the author cannot prove reachability on the genuine
constraint system without first extracting Liu's E. Recorded as a refutation.
