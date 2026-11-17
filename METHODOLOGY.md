# Methodology

## The quantity being forecast

Concurrent live viewers in the Twitch category of a game, averaged over each UTC hour of
its release day. The final case is Grand Theft Auto VI (Twitch game id 1867279146),
releasing 2026-11-19 on PlayStation 5 and Xbox Series X|S, single-player. The game unlocks
at midnight local time, country by country — New Zealand first at 2026-11-18T11:00:00Z,
central Europe at 23:00Z, the UK at 00:00Z, the US east coast at 05:00Z and the west coast
at 08:00Z — so the UTC day contains most of the world's unlock wave, with the largest
Twitch market (the US) arriving in hours 6–9 and peaking in the evening.

The program sees only what a case file carries: the target's own recorded history up to the
end of hour 1 (including hour 1's count), and the hourly curves of past launches from 14
days before to 3 days after their release days. It must therefore forecast *relative* to
hour 1: the shape of the day, not its absolute scale.

## Why hour 1 is not enough on its own

Across the 37 usable past launches in the kit's data, the ratio of the day's peak to hour 1
ranges from 1.00 (ELDEN RING, whose PC unlock landed just before the UTC day) to over 100
(games like Hollow Knight: Silksong, whose single global unlock fell in the middle of the
UTC day, leaving hour 1 nearly empty). What separates those regimes is observable before
hour 2 begins:

- **How much of the unlock wave has already arrived.** A rolling midnight-local launch has
  been playable in New Zealand/Asia for ~13 hours by 00:00 UTC, and Europe joins in the
  last pre-day hour. The viewers in that last hour, relative to hour 1, measure the wave's
  momentum.
- **Whether the category was already hot.** Early-access launches (Hogwarts Legacy,
  Diablo IV, Starfield) entered release day with the category already near its release-day
  level for days; their curves are flat (peak/hour-1 ≈ 1.1–1.3). A clean launch starts from
  a near-zero baseline and keeps climbing as regions unlock.
- **The size of hour 1 itself.** Bigger launches bend less: among rolling console launches,
  peak/hour-1 is ~1.7 for God of War Ragnarök (hour 1 = 269,517) and ~3.2 for Red Dead
  Redemption 2 (hour 1 = 116,550), while smaller, US-skewed launches bend more (Marvel's
  Wolverine: 9.1 from an hour 1 of 23,357).

## The model

1. **Donors.** Every comparable with a complete, positive release-day curve (at least 20 of
   24 hours, in practice 37 of the 38 in a practice case; the target game's own pre-release
   category history is excluded — it is not a launch curve). Donor *d* contributes
   log-ratios `r_d[h] = ln(v_d[h] / v_d[1])` for h = 2..24.
2. **Situation features** (log space, computed identically for donors and target):
   - `logp1 = ln(hour 1 viewers)`;
   - `m1 = ln(viewers in the last hour before release day / hour 1)`;
   - `base = ln(median hourly viewers 72–24 h before release / hour 1)`.
3. **Kernel weights.** `w_d = exp(-0.5 * sum_k ((f_dk - f_tk) / s_k)^2)` over the features
   both sides have, with scales `s = {logp1: 0.6, m1: 0.7, base: 1.0}`.
4. **Quantiles.** For each hour, the five forecast quantiles are the weighted empirical
   quantiles of the donors' `r_d[h]`, mapped back through the target's hour 1, with the
   median amplified by `alpha = 1.04` and deviations from the median shrunk by
   `beta = 0.78`. The shrink is the honest correction for a known bias: cross-game
   dispersion mixes genuine within-day uncertainty with residual situation mismatch, so
   raw donor quantiles are systematically too wide (on the practice set, beta = 1.0 costs
   ~0.009 of loss against beta = 0.78).
5. **Fallback.** Any failure in the model path degrades to a persistence forecast (flat at
   hour 1, lognormal spread widening as `0.15 * sqrt(h - 1)`), so a case is never invalid.

Everything is deterministic: fixed iteration order, no randomness, no clock, no network,
Python 3.13 standard library only. A full run over the four practice cases takes ~0.7 s.

## Calibration and validation

Calibration used only the four practice launches shipped in the kit (Marvel's Wolverine
2026-09-15, Red Dead Redemption 2 2018-10-26, God of War Ragnarök 2022-11-09, Marvel's
Spider-Man 2 2023-10-20). Each was forecast from its own case file (donor pool = that
case's 38 comparables, which exclude all four practice launches) and scored against the
launch's actual hourly counts from the same source the kit used (SullyGnome's hourly
category averages, fetched 2026-11-17). Scoring is the competition's own rule: mean pinball
loss on the log scale over hours 2–24 × 5 quantiles. The scoring implementation was verified
by reproducing the house baseline's published practice loss (0.3871 computed vs "~0.387"
stated in the rules).

| case | this model | house baseline |
|---|---|---|
| Marvel's Wolverine | 0.242 | 0.744 |
| Red Dead Redemption 2 | 0.124 | 0.287 |
| God of War Ragnarök | 0.140 | 0.215 |
| Marvel's Spider-Man 2 | 0.205 | 0.303 |
| **mean** | **0.178** | **0.387** |

Ablations on the same set: unweighted all-donor ratio quantiles 0.324; adding size
weighting only 0.245; adding the pre-day momentum feature 0.235; adding the baseline-heat
feature 0.187; final alpha/beta calibration 0.178. The hardest case is Wolverine — a
small, US-skewed launch whose day bends 9× — and the model still halves the baseline's
loss there.

## What this implies for GTA VI's day

The forecast scales with whatever hour 1 prints, so the model's content is the *shape* it
assigns. For a large rolling console launch (the situation GTA VI is in: no early access,
console-only, midnight-local unlocks), the matched donors (Red Dead Redemption 2, God of
War Ragnarök, Marvel's Spider-Man 2, the Call of Duty launches) put the median curve
rising through the US unlocks (hours 6–9), dipping slightly in the late UTC morning, then
climbing to a peak around hours 19–21 at roughly 2–2.5× hour 1, before easing into hour 24.
For scale: the largest hour-1 prints in the comparable set are Cyberpunk 2077's 851,999
(2020) and ELDEN RING's 875,155 (2022); GTA VI's category already showed ~1,240 viewers
with 181 live channels a full two days before release (kit probe, 2026-11-17T03:10Z), so
its hour 1 — printed after Europe and the UK have unlocked — should land in the
high-hundreds-of-thousands range typical of the biggest launches, with the model's median
peak then falling in the 1.5–2.5M range. Those absolute numbers are expectations, clearly
labelled as such; the submitted program itself derives everything from the case file it is
given on the day.

## Data sources

- Case data (histories and comparables): the competition kit's input files, sourced by the
  organisers from SullyGnome.com's hourly Twitch category averages (viewers and channels),
  read 2026-11-17; the final case's history and hour 1 come from the organisers' own
  once-a-minute recorder of Twitch's public directory count for game id 1867279146.
- Practice answers used for validation: SullyGnome hourly "Average viewers" for the four
  practice games' release months, fetched 2026-11-17 via the API the kit's NOTICE.txt
  documents. Sanity check: the fetched Red Dead Redemption 2 hour 1 (116,550) equals the
  kit case's known print exactly.
- Launch timing (unlock waves, platforms): the competition rules and each case's `notes`
  and comparables' `unlock` fields, which cite contemporary reporting (GameSpot,
  GamesRadar, beebom, and similar).
