"""Constants for the KBG Turf Risk integration."""

DOMAIN = "kbg_turf_risk"

CONF_TEMP_SENSOR = "temp_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_GDD_BASE_F = "gdd_base_f"
CONF_NAME = "name"

DEFAULT_NAME = "KBG Turf Risk"
DEFAULT_GDD_BASE_F = 32.0  # cool-season default base temp, Fahrenheit

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

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_data"

SIGNAL_UPDATE = f"{DOMAIN}_update"

# How many days of daily-average history to retain (5 needed for Smith-Kerns,
# kept a bit longer as a buffer/for future models)
HISTORY_DAYS_KEPT = 10
