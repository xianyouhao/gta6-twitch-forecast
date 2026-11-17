# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/xianyouhao/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/xianyouhao/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

A deterministic, standard-library-only program that forecasts a game's release-day Twitch
audience hour by hour. Given one case file — everything recorded up to the end of hour 1 of
the release day (UTC), hour 1's concurrent-viewer count included, plus the full hourly
curves of dozens of past big launches — it writes, for each of hours 2–24, five quantiles
(0.05, 0.25, 0.5, 0.75, 0.95) of that hour's concurrent viewers in the game's Twitch
category.

The model is a situation-matched donor pool. Each past launch with a complete release-day
curve is reduced to log-ratios against its own hour 1, then weighted by a Gaussian kernel
over three features computed identically for donor and target from the case's own data: the
size of hour 1, how much of the regional unlock wave had already arrived in the last hour
before the UTC day began, and how hot the category already was in the days before release
(which separates clean launches from early-access ones). The forecast's log-quantiles are
the weighted empirical quantiles of the matched donors' ratios, with the median slightly
amplified and the spread slightly shrunk — both calibrated on the four practice launches
shipped in the competition kit, where the program scores a mean pinball loss of 0.178
against the house persistence baseline's 0.387. Full method, data sources and validation:
[METHODOLOGY.md](METHODOLOGY.md).

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`input/` must hold one or more case files (`<id>.in`, schema `makefun/twitch-ccu-case/v1`);
the program reads every one of them in name order and writes one `<id>.out` per case to the
output directory. With no environment variables set it reads `/input` and writes `/output`,
as the grader runs it. Python 3.13, standard library only, no network; two runs of the same
case produce byte-identical output.

---

<sub>Entered on [make.fun](https://make.fun/?ref=mked774b&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
