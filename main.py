"""Hour-by-hour Twitch CCU forecast for a game's release day (make.fun gta6-twitch-ccu-forecast-01).

The program is run once per case in a sandbox with no network. A case file gives us, for one
launch: everything recorded up to the end of hour 1 of the release day (UTC), hour 1's viewer
count included, plus the full hourly curves of dozens of past big launches ("comparables")
around their own release days. For each of hours 2..24 we must write five quantiles
(0.05, 0.25, 0.5, 0.75, 0.95) of that hour's concurrent-viewer count. Scoring is the mean
pinball loss on the natural-log scale, so all modelling happens in log space.

Method (see METHODOLOGY.md for the full write-up and the validation numbers):

1.  Every comparable with a complete release-day curve becomes a donor. Its curve is reduced
    to log-ratios against its own hour 1: r_d[h] = ln(v_d[h] / v_d[1]).
2.  A donor only helps if its launch *situation* resembles the target's, so donors are
    weighted by a Gaussian kernel over three log-space features, computed identically for
    donors and for the target from data the case itself carries:
      - logp1: the size of hour 1 itself (big launches bend differently from small ones);
      - m1:    ln(viewers in the last hour before release day / hour 1) -- how much of the
               unlock wave had already arrived when the UTC day began;
      - base:  ln(median hourly viewers 3..1 days before release / hour 1) -- separates
               clean launches (baseline near zero) from early-access launches whose
               category was already hot for days.
3.  For each hour, the forecast's log-quantiles are the weighted empirical quantiles of the
    donors' r_d[h], with the median slightly amplified (alpha) and the spread slightly
    shrunk (beta): cross-game dispersion overstates one known game's uncertainty, because
    part of it is situation mismatch the kernel cannot fully remove. alpha and beta were
    calibrated on the four practice launches in the kit (leave-the-target-out donor pools):
    practice pinball loss 0.178 against the house persistence baseline's 0.387.

Any failure in the model path for a case falls back to a persistence forecast (every hour
stays at hour 1's count with a slowly widening lognormal spread), so a case is never left
invalid by an exception. The program is deterministic: fixed iteration order, no randomness,
no clock, no network, standard library only.
"""

import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]

# Kernel scales for the three situation features (log units), calibrated on the practice set.
SCALES = {"logp1": 0.6, "m1": 0.7, "base": 1.0}
# Median amplification / spread shrink applied to the weighted donor quantiles.
ALPHA = 1.04
BETA = 0.78
# A donor needs at least this many of the release day's 24 hours to be usable.
MIN_DAY_HOURS = 20


def parse_ts(ts):
    """Parse the case files' ISO-8601 UTC timestamps ('2026-11-19T00:00:00Z')."""
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def hour_buckets(points, day_start):
    """points: iterable of (datetime, viewers). Returns {hour offset from day_start: mean}."""
    buckets = {}
    for t, v in points:
        off = int((t - day_start).total_seconds() // 3600)
        buckets.setdefault(off, []).append(v)
    return {k: sum(vs) / len(vs) for k, vs in buckets.items()}


def situation(buckets, p1):
    """The three kernel features, in log space, for one launch whose hour 1 is p1."""
    feats = {"logp1": math.log(max(p1, 1.0))}
    last = buckets.get(-1)
    if last:
        feats["m1"] = math.log(last / p1)
    pre = [v for off, v in buckets.items() if -72 <= off < -24 and v > 0]
    if pre:
        feats["base"] = math.log(statistics.median(pre) / p1)
    return feats


def donor_from_comparable(comp, target_name):
    """Reduce one comparable to its release-day curve + situation features, or None."""
    name = comp.get("name", "")
    if name == target_name or name.startswith(target_name):
        return None  # the target's own pre-release history is not a launch curve
    day_start = parse_ts(comp["day_start"])
    points = [(parse_ts(p["from"]), p["viewers"]) for p in comp["hourly"]]
    buckets = hour_buckets(points, day_start)
    curve = {off + 1: v for off, v in buckets.items() if 0 <= off < 24}
    if len(curve) < MIN_DAY_HOURS or curve.get(1, 0) <= 0:
        return None
    if any(curve.get(h, 0) <= 0 for h in range(1, 25)):
        return None
    return {"curve": curve, "p1": curve[1], "feats": situation(buckets, curve[1])}


def weighted_quantile(pairs, tau):
    """Weighted quantile of (value, weight) pairs, linear interpolation on the CDF."""
    pairs = sorted(pairs)
    total = sum(w for _, w in pairs)
    if total <= 0:
        return pairs[len(pairs) // 2][0]
    target = tau * total
    acc = 0.0
    for i, (v, w) in enumerate(pairs):
        acc += w
        if acc >= target:
            if i == 0:
                return v
            prev_v, _ = pairs[i - 1]
            frac = (target - (acc - w)) / w if w > 0 else 0.0
            return prev_v + frac * (v - prev_v)
    return pairs[-1][0]


def target_buckets(case, day_start):
    """The target's own hourly buckets from its history.

    Practice cases and the final both carry history_hourly (whole-hour means). If a case
    ever lacked it, fall back to the raw history points (minute reads in the final),
    bucketed the same way, so the situation features still see the unlock wave.
    """
    rows = case.get("history_hourly") or []
    points = [(parse_ts(r["from"]), r["viewers"]) for r in rows]
    buckets = hour_buckets(points, day_start)
    if not buckets:
        raw = [(parse_ts(p["at"]), p["viewers"]) for p in case.get("history") or []]
        buckets = hour_buckets(raw, day_start)
    return buckets


def model_forecast(case, p1):
    """The donor-kernel forecast: {hour: [5 quantiles]} for hours 2..24."""
    day_start = parse_ts(case["day_start"])
    target_feats = situation(target_buckets(case, day_start), p1)

    donors = []
    for comp in case["comparables"]:
        d = donor_from_comparable(comp, case["game"]["name"])
        if d is None:
            continue
        dist2 = 0.0
        shared = 0
        for key, scale in SCALES.items():
            if key in d["feats"] and key in target_feats:
                dist2 += ((d["feats"][key] - target_feats[key]) / scale) ** 2
                shared += 1
        weight = math.exp(-0.5 * dist2) if shared else 1.0
        donors.append((d, max(weight, 1e-6)))
    if len(donors) < 3:
        raise ValueError("not enough usable donors")

    out = {}
    for h in range(2, 25):
        pairs = [(math.log(d["curve"][h] / d["p1"]), w) for d, w in donors if h in d["curve"]]
        med = weighted_quantile(pairs, 0.5)
        row = []
        for tau in LEVELS:
            q = weighted_quantile(pairs, tau)
            row.append(p1 * math.exp(ALPHA * med + BETA * (q - med)))
        out[h] = row
    return out


def persistence_forecast(p1):
    """Fallback: every hour stays at hour 1's count, lognormal spread widening as sqrt(h-1)."""
    z = [-1.645, -0.674, 0.0, 0.674, 1.645]
    return {h: [p1 * math.exp(zi * 0.15 * math.sqrt(h - 1)) for zi in z] for h in range(2, 25)}


def round2(x):
    """Round to 2 decimals, half up; whole numbers come back as ints (compact JSON)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if float(value).is_integer() else value


def clean_row(values):
    """Enforce the output contract: finite, in (0, 1e9], non-decreasing."""
    row = []
    prev = 0.0
    for v in values:
        v = float(v)
        if not math.isfinite(v) or v <= 0:
            v = prev if prev > 0 else 1.0
        v = min(v, 1_000_000_000.0)
        v = max(v, prev)
        row.append(round2(v))
        prev = float(row[-1])
    return row


def forecast_case(case):
    known = case["known"]
    if isinstance(known, dict):
        known = [known]
    first = next((k for k in known if k.get("hour") == 1), None)
    if first is None:
        raise ValueError("case has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    try:
        raw = model_forecast(case, p1)
    except Exception:
        raw = persistence_forecast(p1)
    hours = []
    for row in sorted(case["forecast"], key=lambda r: r["hour"]):
        h = row["hour"]
        hours.append({"hour": h, "q": clean_row(raw[h])})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    sys.exit(main())
