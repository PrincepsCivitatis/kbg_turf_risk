# KBG Turf Risk

A custom Home Assistant integration that computes **Growing Degree Days**,
several turf disease risk models, an irrigation deficit indicator, and a
chinch bug pressure indicator — **entirely from sensors you already have in
HA** (e.g. your Ecowitt integration's outdoor temperature, humidity,
rainfall, and soil moisture entities). No WeeWX/InfluxDB/Grafana stack, no
Syngenta GreenCast subscription required.

## What it computes

| Entity | What it is |
|---|---|
| `sensor.kbg_turf_risk_gdd_cumulative` | Running total Growing Degree Days (base 0C/32F, cool-season), resettable |
| `sensor.kbg_turf_risk_gdd_today_in_progress` | Today's GDD so far, updates live as new samples arrive |
| `sensor.kbg_turf_risk_dollar_spot_risk` | 0-100% probability from the **Smith-Kerns model** (Smith & Kerns, 2018, *PLOS ONE*) |
| `sensor.kbg_turf_risk_pythium_blight_risk_hours_today` | Hours today meeting the Pythium risk window |
| `sensor.kbg_turf_risk_brown_patch_risk_hours_today` | Hours today meeting the Brown Patch (*Rhizoctonia solani*) sustained warm/humid threshold |
| `sensor.kbg_turf_risk_fusarium_patch_risk_hours_today` | Hours today meeting the Fusarium/Microdochium Patch sustained cool/wet threshold |
| `sensor.kbg_turf_risk_red_thread_risk_hours_today` | Hours today meeting the Red Thread sustained mild/wet threshold |
| `sensor.kbg_turf_risk_chinch_bug_pressure_consecutive_hot_dry_days` | Consecutive hot (and dry, if a rain sensor is configured) days |
| `sensor.kbg_turf_risk_irrigation_deficit_7_day` | *(requires a rain sensor)* Inches still needed this week to hit the cool-season watering target |
| `sensor.kbg_turf_risk_soil_moisture` | *(requires a soil moisture sensor)* Passthrough of your configured soil moisture entity |
| `binary_sensor.kbg_turf_risk_dollar_spot_action_threshold_exceeded` | On when Dollar Spot risk >= 20% (the model's published action threshold) |
| `binary_sensor.kbg_turf_risk_pythium_blight_high_risk` | On when the Pythium criteria were met on the most recently completed day |
| `binary_sensor.kbg_turf_risk_brown_patch_high_risk` | On when the Brown Patch criteria were met on the most recently completed day |
| `binary_sensor.kbg_turf_risk_fusarium_patch_high_risk` | On when the Fusarium Patch criteria were met on the most recently completed day |
| `binary_sensor.kbg_turf_risk_red_thread_high_risk` | On when the Red Thread criteria were met on the most recently completed day |
| `binary_sensor.kbg_turf_risk_chinch_bug_elevated_pressure` | On after 5+ consecutive hot/dry days |
| `binary_sensor.kbg_turf_risk_irrigation_needed` | *(requires a rain sensor)* On when the 7-day rainfall total is below the target |
| `binary_sensor.kbg_turf_risk_soil_moisture_low` | *(requires a soil moisture sensor)* On when soil moisture is below the configured threshold |

## The models, and why they're implemented this way

**Growing Degree Days**: `GDD = ((daily_max_C + daily_min_C) / 2) - base_temp_C`,
floored at zero, accumulated daily. Base temp defaults to 0C/32F for
cool-season turf, matching standard extension-service guidance. Configurable
in Fahrenheit in the config flow for convenience; all internal math is in
Celsius.

**Dollar Spot — Smith-Kerns model** (Smith, D.L. and Kerns, J.P., et al.,
2018, "Development and validation of a weather-based warning system to
advise fungicide applications to control dollar spot on turfgrass," *PLOS
ONE* 13(3)):

```
Logit(u) = -11.4041 + 0.0894 x MEANRH + 0.1932 x MEANAT(Celsius)
Probability (%) = e^Logit / (1 + e^Logit) x 100
```

`MEANRH` and `MEANAT` are 5-day rolling averages of daily average relative
humidity and daily average air temperature. The published action threshold
is 20% — field validation showed spraying at that threshold gave control
comparable to a calendar-based program while cutting applications up to
30%. **The model is not validated outside a 5-day average temperature of
10-35C**; the sensor reports `unknown`/`None` rather than a number outside
that range or before 5 days of history exist, instead of extrapolating.

**Pythium Blight — Nutter-Shane model** (Nutter, F.W., Cole, H., and Schein,
R.D., 1983, "Disease forecasting system for warm weather Pythium blight of
turfgrass," *Plant Disease* 67:1126-1138): high risk when the day's maximum
temperature exceeds 30C (86F), followed by at least 14 continuous hours
where relative humidity exceeds 90% while temperature stays above 20C
(68F). This is a threshold/criteria model, not a logistic probability like
Dollar Spot — the risk hours sensor tells you how close you got; the binary
sensor tells you whether the full criteria were met on the last completed
day.

**Brown Patch, Fusarium/Microdochium Patch, Red Thread** — these three
fungal diseases don't have a single published logistic model the way Dollar
Spot does, so they're modeled the same way as Pythium: a sustained-hours
threshold within a temperature band, drawn from standard turf pathology
extension guidance rather than a specific peer-reviewed paper.

- **Brown Patch** (*Rhizoctonia solani*): temp >= 20C (68F) with >= 10
  cumulative hours/day of RH >= 95%. Favors warm, humid nights.
- **Fusarium/Microdochium Patch** (*Microdochium nivale*): temp between
  0-15C (32-59F) with >= 10 cumulative hours/day of RH >= 90%. The opposite
  end of the temperature range from Pythium/Brown Patch — common in cool,
  wet spring/fall/winter conditions.
- **Red Thread** (*Laetisaria fuciformis*): temp between 15-25C (59-77F)
  with >= 12 cumulative hours/day of RH >= 90%. Note: Red Thread is also
  strongly favored by low nitrogen fertility, which isn't modeled here —
  treat this as the weather half of the picture, not the whole risk.

**Chinch Bug Pressure** (hairy chinch bug, *Blissus* spp.) — not a disease,
but the other major weather-driven cool-season KBG pest: activity and
damage increase on hot, dry, drought-stressed turf. Modeled as consecutive
days where max temp exceeds 29.4C (85F); if a rain sensor is configured, a
day only counts toward the streak if it was also dry (< 2mm/~0.08in of
rain that day). Flags elevated pressure at 5+ consecutive qualifying days.

**Irrigation Deficit** *(requires a rain sensor)* — sums your rain sensor's
daily totals over the trailing 7 days and compares against a configurable
weekly target (default 1.25in), following the standard cool-season turf
extension guidance of ~1-1.5in/week from rain + irrigation combined
(e.g. Purdue, Rutgers NJAES, and University of Illinois Extension lawn
watering guides). Positive = shortfall, negative = surplus. Point your rain
sensor at whatever entity mirrors Ecowitt's own "rain day" total (already
resets at local midnight) — this integration reads that value at rollover
rather than re-integrating a rain rate itself.

**Soil Moisture** *(requires a soil moisture sensor)* — direct passthrough
of a configured Ecowitt soil moisture entity (e.g. a WH51 probe), plus a
configurable low-moisture threshold (default 25%) for the binary sensor.

## Install (HACS custom repository)

1. HACS -> the three-dot menu (top right) -> Custom repositories
2. Add this repo URL, category: Integration
3. Search for "KBG Turf Risk" in HACS, install, restart Home Assistant
4. Settings -> Devices & Services -> Add Integration -> "KBG Turf Risk"
5. Pick your existing Ecowitt outdoor temperature and outdoor humidity
   sensor entities (required), optionally a rainfall entity (enables the
   irrigation deficit sensor) and a soil moisture entity (enables the soil
   moisture sensors), set your GDD base temp (default 32F is correct for
   cool-season KBG), irrigation target, and soil moisture low threshold,
   and submit

## Important operational notes

- **Sampling cadence matters.** The integration listens for state changes
  on your two chosen entities and does time-weighted accumulation between
  samples (capped at 1 hour per gap so a dropped Ecowitt connection can't
  fabricate hours of Pythium "risk" on reconnect). Your Ecowitt push
  interval (commonly ~60s) is more than sufficient.
- **Daily rollover happens at local midnight.** If Home Assistant restarts
  exactly at midnight and misses the scheduled callback, the next incoming
  sensor sample will trigger the rollover as a safety net.
- **History is stored locally** via HA's storage helpers (survives
  restarts) and keeps the last 10 days — only 5 are needed for the Dollar
  Spot model, the rest is buffer.
- **Reset the GDD counter** with the `kbg_turf_risk.reset_gdd` service —
  call it after any PGR application or whenever you want the cumulative
  count to restart (e.g. spring green-up).
- Use the two binary sensors directly in Node-RED or HA automations to
  trigger a notification ("consider a preventative fungicide app") rather
  than automating an actual chemical application — that decision should
  stay a human one.
