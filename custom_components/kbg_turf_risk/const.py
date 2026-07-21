"""Constants for the KBG Turf Risk integration."""

DOMAIN = "kbg_turf_risk"

CONF_TEMP_SENSOR = "temp_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_RAIN_SENSOR = "rain_sensor"
CONF_SOIL_MOISTURE_SENSOR = "soil_moisture_sensor"
CONF_GDD_BASE_F = "gdd_base_f"
CONF_IRRIGATION_TARGET_IN = "irrigation_target_in"
CONF_SOIL_MOISTURE_LOW_PCT = "soil_moisture_low_pct"
CONF_NAME = "name"

DEFAULT_NAME = "KBG Turf Risk"
DEFAULT_GDD_BASE_F = 32.0  # cool-season default base temp, Fahrenheit
DEFAULT_IRRIGATION_TARGET_IN = 1.25  # cool-season turf, mid-range of the
# widely cited 1-1.5in/week (rain + irrigation combined) extension guidance
# (e.g. Purdue, Rutgers NJAES, Univ. of Illinois Extension lawn watering guides)
DEFAULT_SOIL_MOISTURE_LOW_PCT = 25.0  # below this, cool-season turf is
# typically showing drought stress (extension guidance rule of thumb;
# exact wilting point varies by soil type)

# Smith-Kerns Dollar Spot Model (Smith & Kerns, 2018, PLOS ONE)
# Logit(mu) = -11.4041 + 0.0894 * MEANRH + 0.1932 * MEANAT(Celsius)
# MEANRH / MEANAT = 5-day moving averages of daily average RH% and daily average air temp (C)
DOLLAR_SPOT_INTERCEPT = -11.4041
DOLLAR_SPOT_RH_COEF = 0.0894
DOLLAR_SPOT_AT_COEF = 0.1932
DOLLAR_SPOT_MIN_VALID_C = 10.0
DOLLAR_SPOT_MAX_VALID_C = 35.0
DOLLAR_SPOT_ACTION_THRESHOLD = 20.0  # published action threshold, percent

# Pythium Blight - Nutter-Shane model (Nutter, Cole & Schein, 1983, Plant Disease 67:1126-1138)
# High risk: max daily temp > 30C, followed by >= 14h of RH > 90% while temp stays > 20C
PYTHIUM_MAX_TEMP_C = 30.0
PYTHIUM_MIN_TEMP_C = 20.0
PYTHIUM_RH_THRESHOLD = 90.0
PYTHIUM_HOURS_REQUIRED = 14.0

# Brown Patch - Rhizoctonia solani. No single published logistic model like
# Smith-Kerns exists; this is the widely used extension-guidance threshold
# (e.g. Vargas, "Management of Turfgrass Diseases"; NC State/Clemson turf
# pathology extension): warm, humid nights sustained over time. High risk
# when nighttime/daily temp stays >= 20C (68F) with >= 10 cumulative hours
# of RH >= 95% in a day. Sustained-hours criteria, not a probability.
BROWN_PATCH_MIN_TEMP_C = 20.0
BROWN_PATCH_RH_THRESHOLD = 95.0
BROWN_PATCH_HOURS_REQUIRED = 10.0

# Fusarium Patch / Microdochium Patch - Microdochium nivale. Extension
# guidance (e.g. UMass/Rutgers turf pathology fact sheets) describes this as
# a cool, wet disease, active in the 0-15C (32-59F) band with prolonged leaf
# wetness/high humidity. Sustained-hours threshold, same shape as Pythium's
# but for the opposite (cool) end of the temperature range.
FUSARIUM_PATCH_MIN_TEMP_C = 0.0
FUSARIUM_PATCH_MAX_TEMP_C = 15.0
FUSARIUM_PATCH_RH_THRESHOLD = 90.0
FUSARIUM_PATCH_HOURS_REQUIRED = 10.0

# Red Thread - Laetisaria fuciformis. Extension guidance (e.g. Purdue,
# Rutgers turf pathology fact sheets) favors cool, wet, humid conditions in
# roughly the 15-25C (59-77F) band with extended leaf wetness; most common
# on slow-growing, nitrogen-deficient turf, which this integration cannot
# measure, so only the weather-side sustained-hours criteria are modeled.
RED_THREAD_MIN_TEMP_C = 15.0
RED_THREAD_MAX_TEMP_C = 25.0
RED_THREAD_RH_THRESHOLD = 90.0
RED_THREAD_HOURS_REQUIRED = 12.0

# Chinch bug (Blissus spp., esp. hairy chinch bug) pressure. Turf entomology
# extension guidance (e.g. Purdue, Michigan State) associates elevated
# activity/damage with hot, sunny, drought-stressed turf. Modeled here as
# consecutive days where max temp exceeds ~29.4C (85F); if a rain sensor is
# configured, a day only counts toward the streak when it was also dry
# (< 2mm / ~0.08in), since drought-stressed turf is the real risk factor.
CHINCH_BUG_HOT_TEMP_C = 29.4
CHINCH_BUG_DRY_RAIN_MM = 2.0
CHINCH_BUG_CONSECUTIVE_DAYS_REQUIRED = 5

# Irrigation deficit window, days
IRRIGATION_WINDOW_DAYS = 7

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_data"

SIGNAL_UPDATE = f"{DOMAIN}_update"

# How many days of daily-average history to retain (5 needed for Smith-Kerns,
# kept a bit longer as a buffer/for future models)
HISTORY_DAYS_KEPT = 10
