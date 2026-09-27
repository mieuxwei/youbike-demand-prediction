# Figure and screenshot provenance

These assets illustrate the project. Screenshots are captures of its actual published interface, not generated mockups, new datasets or evaluation evidence.

| Asset | Source and scope |
|---|---|
| [Track A model comparison](track-a-model-comparison.svg) | Existing repository figure, unchanged. December 2023 holdout; 100 training-selected stations; 74,282 station-hour rows. Values from [saved metrics](../../results/model_comparison_metrics.csv). |
| [Live availability](live-availability-20260927.png) | Captured from the [published site](https://youbike-demand-observatory.rwhqgqfdk2.chatgpt.site/#live) on 2026-09-27 at approximately 18:04 Asia/Taipei. First fixed station, 捷運科技大樓站 (`500101001`), selected by the existing fixed ordering, not its score. |
| [Static redistribution](static-redistribution-20260927.png) | Captured from the same published site on 2026-09-27 at approximately 18:05 Asia/Taipei. First chronological scenario: 2026-09-14 07:00 Asia/Taipei; base constraints; MILP selected. |

## Live image

The UI shows 13 current bikes / 15 return spaces, 30m persistence 13 and 60m HGB 13.1. Source time is 2026-09-27 17:59:52, scheduled origin 18:00:32, fetch start/completion 18:00:32 / 18:00:37, and forecast targets 18:30:32 / 19:00:32 (all Asia/Taipei). These are captured values, not current data or measured errors. The screenshot retains the source-age and estimate labels.

The station selector covers the original 12-station cohort; the image shows one selected station, not twelve simultaneous cards. No station was removed, no failed result was replaced and no model was retrained for this image.

## Simulation image

The recorded observation is `2026-09-13T23:00:21+00:00`; base limits are 12 moved bikes and 30 bike-km, distance weight 0.1 and handling penalty 0.05. No transfer yields objective 76.877; greedy and MILP both yield 71.343 and move three bikes. These values describe one saved scenario. They differ from the headline means across all twelve scenarios.

Simulation assumes immediate transfers and a half-capacity inventory target. It is not a current dispatch recommendation or an observed operational benefit.

## Rights and capture method

Original interface and visualization: this repository's author, under the repository [MIT License](../../LICENSE). Station observations originate from [Taipei YouBike 2.0 open data](https://data.taipei/dataset/detail?id=c6bc8aed-557d-41d5-bfb1-8da24f78f2fb); upstream terms remain separate.

Screenshots were captured through the browser from Sites version 3. Only normal interface selection and scrolling were used; no text, metrics, styles, DOM or data were replaced. The live image is a section capture; the simulation image is a viewport capture. No research bundle was regenerated.
