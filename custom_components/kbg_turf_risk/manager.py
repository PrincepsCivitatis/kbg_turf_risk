"""Data manager for KBG Turf Risk.

Listens to sensor entities already in Home Assistant (e.g. your Ecowitt
integration's outdoor temp/humidity/rain/soil-moisture sensors), accumulates
daily statistics locally, and computes:

  - Growing Degree Days (daily + cumulative, resettable)
  - Smith-Kerns Dollar Spot risk probability (Smith & Kerns, 2018, PLOS ONE)
  - Pythium Blight risk (Nutter-Shane model, Nutter/Cole/Schein, 1983)
  - Brown Patch, Fusarium/Microdochium Patch, and Red Thread risk
    (extension-guidance sustained temperature/humidity thresholds)
  - Irrigation deficit (7-day rainfall vs. cool-season turf water need)
  - Chinch bug pressure (consecutive hot/dry days)
  - Soil moisture passthrough + low-moisture flag

Temp/humidity math is done in Celsius internally to match the published
disease models; the configured GDD base temperature may be entered in
Fahrenheit for convenience and is converted on load. Rainfall/soil moisture
are optional - if those entities aren't configured, the corresponding
outputs stay unavailable rather than guessing.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, State, Event, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    STORAGE_VERSION,
    STORAGE_KEY_PREFIX,
    SIGNAL_UPDATE,
    HISTORY_DAYS_KEPT,
    DOLLAR_SPOT_INTERCEPT,
    DOLLAR_SPOT_RH_COEF,
    DOLLAR_SPOT_AT_COEF,
    DOLLAR_SPOT_MIN_VALID_C,
    DOLLAR_SPOT_MAX_VALID_C,
    PYTHIUM_MAX_TEMP_C,
    PYTHIUM_MIN_TEMP_C,
    PYTHIUM_RH_THRESHOLD,
    PYTHIUM_HOURS_REQUIRED,
    BROWN_PATCH_MIN_TEMP_C,
    BROWN_PATCH_RH_THRESHOLD,
    BROWN_PATCH_HOURS_REQUIRED,
    FUSARIUM_PATCH_MIN_TEMP_C,
    FUSARIUM_PATCH_MAX_TEMP_C,
    FUSARIUM_PATCH_RH_THRESHOLD,
    FUSARIUM_PATCH_HOURS_REQUIRED,
    RED_THREAD_MIN_TEMP_C,
    RED_THREAD_MAX_TEMP_C,
    RED_THREAD_RH_THRESHOLD,
    RED_THREAD_HOURS_REQUIRED,
    CHINCH_BUG_HOT_TEMP_C,
    CHINCH_BUG_DRY_RAIN_MM,
    CHINCH_BUG_CONSECUTIVE_DAYS_REQUIRED,
    IRRIGATION_WINDOW_DAYS,
)

_LOGGER = logging.getLogger(__name__)


def _f_to_c(value_f: float) -> float:
    return (value_f - 32.0) * 5.0 / 9.0


def _is_fahrenheit(state: State | None) -> bool:
    if state is None:
        return True  # assume imperial (Ecowitt US default) if unknown
    unit = state.attributes.get("unit_of_measurement", "")
    return "f" in unit.lower()


def _is_millimeters(state: State | None) -> bool:
    if state is None:
        return False  # assume imperial (Ecowitt US default) if unknown
    unit = state.attributes.get("unit_of_measurement", "")
    return "mm" in unit.lower()


def _rain_to_in(value: float, state: State | None) -> float:
    return value / 25.4 if _is_millimeters(state) else value


class TurfRiskManager:
    """Owns all the running state for one configured entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        temp_entity: str,
        humidity_entity: str,
        gdd_base_f: float,
        rain_entity: str | None = None,
        soil_moisture_entity: str | None = None,
        irrigation_target_in: float = 1.25,
        soil_moisture_low_pct: float = 25.0,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.temp_entity = temp_entity
        self.humidity_entity = humidity_entity
        self.rain_entity = rain_entity
        self.soil_moisture_entity = soil_moisture_entity
        self.gdd_base_c = _f_to_c(gdd_base_f)
        self.irrigation_target_in = irrigation_target_in
        self.soil_moisture_low_pct = soil_moisture_low_pct

        self._store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}_{entry_id}")

        # Persisted
        self.history: list[dict[str, Any]] = []  # most recent last
        self.gdd_cumulative_c: float = 0.0
        self._chinch_bug_consecutive_days: int = 0

        # In-memory accumulators for "today"
        self._today: date = dt_util.now().date()
        self._temp_sum = 0.0
        self._temp_count = 0
        self._rh_sum = 0.0
        self._rh_count = 0
        self._temp_max_c: float | None = None
        self._temp_min_c: float | None = None

        # Pythium: seconds today where RH>=90% AND temp>=20C were both true,
        # tracked using zero-order hold between samples.
        self._pythium_seconds_today = 0.0
        # Same zero-order-hold approach for the other sustained-hours models.
        self._brown_patch_seconds_today = 0.0
        self._fusarium_patch_seconds_today = 0.0
        self._red_thread_seconds_today = 0.0
        self._last_sample_time: datetime | None = None
        self._last_temp_c: float | None = None
        self._last_rh: float | None = None
        self._last_rain_day_in: float | None = None
        self._last_soil_moisture_pct: float | None = None

        self._unsub_listeners: list[Any] = []

        # Latest computed outputs, refreshed on every rollover / sample
        self.current_gdd_today_c: float = 0.0
        self.dollar_spot_risk: float | None = None
        self.dollar_spot_valid: bool = False
        self.pythium_risk_hours_today: float = 0.0
        self.pythium_high_risk: bool = False
        self.brown_patch_risk_hours_today: float = 0.0
        self.brown_patch_high_risk: bool = False
        self.fusarium_patch_risk_hours_today: float = 0.0
        self.fusarium_patch_high_risk: bool = False
        self.red_thread_risk_hours_today: float = 0.0
        self.red_thread_high_risk: bool = False
        self.soil_moisture_pct: float | None = None
        self.soil_moisture_low: bool = False
        self.irrigation_deficit_in: float | None = None
        self.irrigation_days_of_data: int = 0
        self.chinch_bug_consecutive_days: int = 0
        self.chinch_bug_elevated_pressure: bool = False

    async def async_setup(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.history = stored.get("history", [])
            self.gdd_cumulative_c = stored.get("gdd_cumulative_c", 0.0)
            self._chinch_bug_consecutive_days = stored.get("chinch_bug_consecutive_days", 0)

        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, [self.temp_entity], self._handle_temp_event
            )
        )
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, [self.humidity_entity], self._handle_humidity_event
            )
        )
        if self.rain_entity:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, [self.rain_entity], self._handle_rain_event
                )
            )
        if self.soil_moisture_entity:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, [self.soil_moisture_entity], self._handle_soil_moisture_event
                )
            )
        # Roll the day over just after local midnight
        self._unsub_listeners.append(
            async_track_time_change(self.hass, self._handle_rollover, hour=0, minute=0, second=10)
        )

        self._recompute_models()

    async def async_unload(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    async def async_reset_gdd(self) -> None:
        self.gdd_cumulative_c = 0.0
        await self._async_persist()
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry_id}")

    # ------------------------------------------------------------------
    # Sample handling
    # ------------------------------------------------------------------

    @callback
    def _handle_temp_event(self, event: Event) -> None:
        new_state: State | None = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return
        try:
            value = float(new_state.state)
        except ValueError:
            return
        value_c = _f_to_c(value) if _is_fahrenheit(new_state) else value
        self._ingest(temp_c=value_c, rh=None)

    @callback
    def _handle_humidity_event(self, event: Event) -> None:
        new_state: State | None = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return
        try:
            value = float(new_state.state)
        except ValueError:
            return
        self._ingest(temp_c=None, rh=value)

    @callback
    def _handle_rain_event(self, event: Event) -> None:
        """Track the entity's own daily rain accumulation (e.g. Ecowitt's
        "rain day" sensor, which Ecowitt itself resets at local midnight)."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return
        try:
            value = float(new_state.state)
        except ValueError:
            return
        self._last_rain_day_in = _rain_to_in(value, new_state)
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry_id}")

    @callback
    def _handle_soil_moisture_event(self, event: Event) -> None:
        new_state: State | None = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return
        try:
            value = float(new_state.state)
        except ValueError:
            return
        self._last_soil_moisture_pct = value
        self.soil_moisture_pct = value
        self.soil_moisture_low = value < self.soil_moisture_low_pct
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry_id}")

    def _ingest(self, temp_c: float | None, rh: float | None) -> None:
        now = dt_util.now()
        today = now.date()
        if today != self._today:
            # Safety net in case the midnight callback was delayed/missed
            # (e.g. HA was restarting right at midnight)
            self._do_rollover(now)

        # Advance the Pythium duration accumulator using the state that was
        # in effect BEFORE this new sample (zero-order hold).
        if self._last_sample_time is not None:
            elapsed = (now - self._last_sample_time).total_seconds()
            elapsed = max(0.0, min(elapsed, 3600.0))  # clamp gaps to 1h so a
            # dropped connection doesn't fabricate hours of "risk" on reconnect
            if (
                self._last_temp_c is not None
                and self._last_rh is not None
                and self._last_temp_c >= PYTHIUM_MIN_TEMP_C
                and self._last_rh >= PYTHIUM_RH_THRESHOLD
            ):
                self._pythium_seconds_today += elapsed
            if (
                self._last_temp_c is not None
                and self._last_rh is not None
                and self._last_temp_c >= BROWN_PATCH_MIN_TEMP_C
                and self._last_rh >= BROWN_PATCH_RH_THRESHOLD
            ):
                self._brown_patch_seconds_today += elapsed
            if (
                self._last_temp_c is not None
                and self._last_rh is not None
                and FUSARIUM_PATCH_MIN_TEMP_C <= self._last_temp_c <= FUSARIUM_PATCH_MAX_TEMP_C
                and self._last_rh >= FUSARIUM_PATCH_RH_THRESHOLD
            ):
                self._fusarium_patch_seconds_today += elapsed
            if (
                self._last_temp_c is not None
                and self._last_rh is not None
                and RED_THREAD_MIN_TEMP_C <= self._last_temp_c <= RED_THREAD_MAX_TEMP_C
                and self._last_rh >= RED_THREAD_RH_THRESHOLD
            ):
                self._red_thread_seconds_today += elapsed

        if temp_c is not None:
            self._temp_sum += temp_c
            self._temp_count += 1
            self._temp_max_c = temp_c if self._temp_max_c is None else max(self._temp_max_c, temp_c)
            self._temp_min_c = temp_c if self._temp_min_c is None else min(self._temp_min_c, temp_c)
            self._last_temp_c = temp_c

        if rh is not None:
            self._rh_sum += rh
            self._rh_count += 1
            self._last_rh = rh

        self._last_sample_time = now
        self._recompute_live_estimate()
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry_id}")

    def _recompute_live_estimate(self) -> None:
        """Cheap running estimate of today's GDD-in-progress, for dashboard feedback."""
        if self._temp_max_c is not None and self._temp_min_c is not None:
            avg = (self._temp_max_c + self._temp_min_c) / 2.0
            self.current_gdd_today_c = max(0.0, avg - self.gdd_base_c)
        self.pythium_risk_hours_today = self._pythium_seconds_today / 3600.0
        self.brown_patch_risk_hours_today = self._brown_patch_seconds_today / 3600.0
        self.fusarium_patch_risk_hours_today = self._fusarium_patch_seconds_today / 3600.0
        self.red_thread_risk_hours_today = self._red_thread_seconds_today / 3600.0

    # ------------------------------------------------------------------
    # Daily rollover
    # ------------------------------------------------------------------

    @callback
    def _handle_rollover(self, now: datetime) -> None:
        self.hass.async_create_task(self._async_do_rollover_and_persist(now))

    async def _async_do_rollover_and_persist(self, now: datetime) -> None:
        self._do_rollover(now)
        await self._async_persist()
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry_id}")

    def _do_rollover(self, now: datetime) -> None:
        if self._temp_count > 0 and self._rh_count > 0 and self._temp_max_c is not None:
            avg_temp_c = self._temp_sum / self._temp_count
            avg_rh = self._rh_sum / self._rh_count
            max_temp_c = self._temp_max_c
            min_temp_c = self._temp_min_c if self._temp_min_c is not None else avg_temp_c
            daily_gdd = max(0.0, ((max_temp_c + min_temp_c) / 2.0) - self.gdd_base_c)
            pythium_hours = self._pythium_seconds_today / 3600.0
            pythium_high = max_temp_c > PYTHIUM_MAX_TEMP_C and pythium_hours >= PYTHIUM_HOURS_REQUIRED
            brown_patch_hours = self._brown_patch_seconds_today / 3600.0
            brown_patch_high = brown_patch_hours >= BROWN_PATCH_HOURS_REQUIRED
            fusarium_patch_hours = self._fusarium_patch_seconds_today / 3600.0
            fusarium_patch_high = fusarium_patch_hours >= FUSARIUM_PATCH_HOURS_REQUIRED
            red_thread_hours = self._red_thread_seconds_today / 3600.0
            red_thread_high = red_thread_hours >= RED_THREAD_HOURS_REQUIRED

            rain_in = self._last_rain_day_in if self.rain_entity else None

            # Chinch bug: hot day, and dry too if we have rainfall data to check.
            is_hot = max_temp_c > CHINCH_BUG_HOT_TEMP_C
            is_dry = True if rain_in is None else (rain_in * 25.4) < CHINCH_BUG_DRY_RAIN_MM
            if is_hot and is_dry:
                self._chinch_bug_consecutive_days += 1
            else:
                self._chinch_bug_consecutive_days = 0

            self.history.append(
                {
                    "date": self._today.isoformat(),
                    "avg_temp_c": round(avg_temp_c, 2),
                    "avg_rh": round(avg_rh, 2),
                    "max_temp_c": round(max_temp_c, 2),
                    "min_temp_c": round(min_temp_c, 2),
                    "gdd": round(daily_gdd, 2),
                    "pythium_risk_hours": round(pythium_hours, 2),
                    "pythium_high_risk": pythium_high,
                    "brown_patch_risk_hours": round(brown_patch_hours, 2),
                    "brown_patch_high_risk": brown_patch_high,
                    "fusarium_patch_risk_hours": round(fusarium_patch_hours, 2),
                    "fusarium_patch_high_risk": fusarium_patch_high,
                    "red_thread_risk_hours": round(red_thread_hours, 2),
                    "red_thread_high_risk": red_thread_high,
                    "rain_in": round(rain_in, 3) if rain_in is not None else None,
                }
            )
            self.history = self.history[-HISTORY_DAYS_KEPT:]
            self.gdd_cumulative_c += daily_gdd
        else:
            _LOGGER.warning(
                "kbg_turf_risk: insufficient samples for %s, skipping daily rollup "
                "(temp_count=%s, rh_count=%s)",
                self._today,
                self._temp_count,
                self._rh_count,
            )

        # Reset today's accumulators
        self._today = now.date()
        self._temp_sum = 0.0
        self._temp_count = 0
        self._rh_sum = 0.0
        self._rh_count = 0
        self._temp_max_c = None
        self._temp_min_c = None
        self._pythium_seconds_today = 0.0
        self._brown_patch_seconds_today = 0.0
        self._fusarium_patch_seconds_today = 0.0
        self._red_thread_seconds_today = 0.0
        self._last_rain_day_in = None
        self.current_gdd_today_c = 0.0
        self.pythium_risk_hours_today = 0.0
        self.brown_patch_risk_hours_today = 0.0
        self.fusarium_patch_risk_hours_today = 0.0
        self.red_thread_risk_hours_today = 0.0

        self._recompute_models()

    # ------------------------------------------------------------------
    # Disease models
    # ------------------------------------------------------------------

    def _recompute_models(self) -> None:
        self._compute_dollar_spot()
        if self.history:
            last = self.history[-1]
            self.pythium_high_risk = bool(last.get("pythium_high_risk", False))
            self.brown_patch_high_risk = bool(last.get("brown_patch_high_risk", False))
            self.fusarium_patch_high_risk = bool(last.get("fusarium_patch_high_risk", False))
            self.red_thread_high_risk = bool(last.get("red_thread_high_risk", False))
        else:
            self.pythium_high_risk = False
            self.brown_patch_high_risk = False
            self.fusarium_patch_high_risk = False
            self.red_thread_high_risk = False

        self._compute_irrigation_deficit()
        self.chinch_bug_consecutive_days = self._chinch_bug_consecutive_days
        self.chinch_bug_elevated_pressure = (
            self._chinch_bug_consecutive_days >= CHINCH_BUG_CONSECUTIVE_DAYS_REQUIRED
        )

    def _compute_irrigation_deficit(self) -> None:
        if not self.rain_entity:
            self.irrigation_deficit_in = None
            self.irrigation_days_of_data = 0
            return

        recent = self.history[-IRRIGATION_WINDOW_DAYS:]
        rain_days = [d["rain_in"] for d in recent if d.get("rain_in") is not None]
        self.irrigation_days_of_data = len(rain_days)
        if not rain_days:
            self.irrigation_deficit_in = None
            return

        total_rain_in = sum(rain_days)
        self.irrigation_deficit_in = round(self.irrigation_target_in - total_rain_in, 2)

    def _compute_dollar_spot(self) -> None:
        recent = self.history[-5:]
        if len(recent) < 5:
            self.dollar_spot_risk = None
            self.dollar_spot_valid = False
            return

        mean_at = sum(d["avg_temp_c"] for d in recent) / 5.0
        mean_rh = sum(d["avg_rh"] for d in recent) / 5.0

        valid_range = DOLLAR_SPOT_MIN_VALID_C <= mean_at <= DOLLAR_SPOT_MAX_VALID_C
        self.dollar_spot_valid = valid_range

        logit = DOLLAR_SPOT_INTERCEPT + (DOLLAR_SPOT_RH_COEF * mean_rh) + (DOLLAR_SPOT_AT_COEF * mean_at)
        try:
            probability = (math.exp(logit) / (1 + math.exp(logit))) * 100.0
        except OverflowError:
            probability = 100.0 if logit > 0 else 0.0

        self.dollar_spot_risk = round(probability, 1)

    async def _async_persist(self) -> None:
        await self._store.async_save(
            {
                "history": self.history,
                "gdd_cumulative_c": self.gdd_cumulative_c,
                "chinch_bug_consecutive_days": self._chinch_bug_consecutive_days,
            }
        )
