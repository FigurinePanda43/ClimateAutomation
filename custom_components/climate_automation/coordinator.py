"""Moteur de décision de Climate Automation.

Le coordinator recalcule, pour chaque clim de chaque zone, l'état désiré, puis
fait converger l'état réel vers cet état. Il remplace les ~1100 lignes de logique
dupliquée de l'automatisation YAML d'origine par une fonction de décision unique.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, time, timedelta

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    COMMAND_VERIFY_DELAY_SECONDS,
    COMPUTED_CONFORT,
    COMPUTED_DISABLED,
    COMPUTED_ECO,
    COMPUTED_HORS_GEL,
    COMPUTED_OFF,
    COMPUTED_PRECHAUFFE_ROUGE,
    DEFAULT_ANTI_COURT_CYCLE_MINUTES,
    DEVICE_MIN_TEMP_SETPOINT,
    DOMAIN,
    HVAC_OFF,
    SOLAR_DEBOUNCE_SECONDS,
    TEMPO_ROUGE,
    UPDATE_INTERVAL_SECONDS,
)
from .models import DesiredState, ZoneConfig, ZoneSettings

_LOGGER = logging.getLogger(__name__)

_OFF_STATES = (HVAC_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN, None, "")


class ClimateAutomationCoordinator(DataUpdateCoordinator[dict[str, DesiredState]]):
    """Pilote l'ensemble des zones et climatiseurs."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        solar_sensor: str,
        tempo_sensor: str,
        zones: dict[str, ZoneConfig],
    ) -> None:
        """Initialise le coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.entry_id = entry_id
        self.solar_sensor = solar_sensor
        self.tempo_sensor = tempo_sensor
        self.zones = zones

        # Réglages ajustables en direct (pilotés par les entités créées).
        self.settings: dict[str, ZoneSettings] = {
            key: ZoneSettings() for key in zones
        }
        self.anti_court_cycle_minutes: float = DEFAULT_ANTI_COURT_CYCLE_MINUTES

        # Activation par clim (interrupteur par clim). Défaut : activée.
        self.clim_enabled: dict[str, bool] = {
            clim: True for zone in zones.values() for clim in zone.climates
        }

        # Suivi interne pour la convergence et l'anti-court-cycle.
        self._last_onoff_change: dict[str, datetime] = {}
        self._applied: dict[str, DesiredState] = {}

        self._unsub_callbacks: list[CALLBACK_TYPE] = []
        self._solar_debounce_unsub: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------ setup
    @callback
    def async_setup_listeners(self) -> None:
        """Enregistre les déclencheurs externes (capteurs)."""
        # Variation de la production solaire -> recalcul (avec debounce).
        self._unsub_callbacks.append(
            async_track_state_change_event(
                self.hass, [self.solar_sensor], self._handle_solar_change
            )
        )
        # Changement de couleur Tempo -> recalcul immédiat.
        self._unsub_callbacks.append(
            async_track_state_change_event(
                self.hass, [self.tempo_sensor], self._handle_immediate_change
            )
        )

    @callback
    def async_unload(self) -> None:
        """Libère les abonnements."""
        for unsub in self._unsub_callbacks:
            unsub()
        self._unsub_callbacks.clear()
        if self._solar_debounce_unsub:
            self._solar_debounce_unsub()
            self._solar_debounce_unsub = None

    @callback
    def _handle_solar_change(self, event: Event) -> None:
        """Recalcul après stabilisation de la production solaire (debounce)."""
        if self._solar_debounce_unsub:
            self._solar_debounce_unsub()

        async def _fire(_now: datetime) -> None:
            self._solar_debounce_unsub = None
            await self.async_request_refresh()

        self._solar_debounce_unsub = async_call_later(
            self.hass, SOLAR_DEBOUNCE_SECONDS, _fire
        )

    @callback
    def _handle_immediate_change(self, event: Event) -> None:
        """Recalcul immédiat (changement Tempo)."""
        self.hass.async_create_task(self.async_request_refresh())

    # ----------------------------------------------------- réglages (entités)
    async def async_set_zone_setting(
        self, zone_key: str, attr: str, value: object
    ) -> None:
        """Met à jour un réglage de zone puis relance le moteur."""
        setattr(self.settings[zone_key], attr, value)
        await self.async_request_refresh()

    async def async_set_anti_court_cycle(self, minutes: float) -> None:
        """Met à jour le délai anti-court-cycle global."""
        self.anti_court_cycle_minutes = minutes

    async def async_set_clim_enabled(self, clim: str, enabled: bool) -> None:
        """Active/désactive une clim et applique immédiatement le changement."""
        self.clim_enabled[clim] = enabled
        await self.async_request_refresh()

    # ------------------------------------------------------------ helpers état
    def _get_solar(self) -> float | None:
        """Production solaire (kW) ou None si indisponible."""
        state = self.hass.states.get(self.solar_sensor)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _get_tempo(self) -> str | None:
        """Couleur Tempo du jour (en minuscules) ou None."""
        state = self.hass.states.get(self.tempo_sensor)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return str(state.state).lower()

    def _resolve_temp_sensor(self, zone: ZoneConfig) -> str | None:
        """Capteur de température de la zone, avec repli sur la 1re zone équipée.

        Si la zone n'a pas de capteur, on utilise celui de la première zone (par
        ordre des clés) qui en possède un — typiquement la zone 1.
        """
        if zone.temp_sensor:
            return zone.temp_sensor
        for key in sorted(self.zones):
            other = self.zones[key]
            if other.temp_sensor:
                return other.temp_sensor
        return None

    def _get_zone_temperature(self, zone: ZoneConfig) -> float | None:
        """Température réelle de la zone (via capteur, repli zone 1)."""
        sensor = self._resolve_temp_sensor(zone)
        if not sensor:
            return None
        state = self.hass.states.get(sensor)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _sunset_stop(self, now: datetime, decalage: time) -> datetime | None:
        """Heure d'extinction du soir = coucher du soleil - décalage."""
        sunset = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, now.date())
        if sunset is None:
            return None
        offset = timedelta(hours=decalage.hour, minutes=decalage.minute)
        return dt_util.as_local(sunset) - offset

    # ---------------------------------------------------------- décision cœur
    def _compute_base(self, zone: ZoneConfig, clim: str, now: datetime) -> DesiredState:
        """Calcule l'état désiré « normal » (mois/horaire/Tempo/solaire), sans hors-gel."""
        s = self.settings[zone.key]

        def on_state(computed: str, temperature: float) -> DesiredState:
            return DesiredState(
                computed=computed,
                hvac_mode=s.hvac_mode,
                temperature=temperature,
                fan_mode=s.fan_mode,
                flux_horizontal=s.flux_horizontal,
                flux_vertical=s.flux_vertical,
            )

        off_state = DesiredState(computed=COMPUTED_OFF, hvac_mode=HVAC_OFF)

        def solar_state() -> DesiredState:
            """Confort/éco/off selon les seuils de production solaire de la zone."""
            solar = self._get_solar()
            if solar is None:
                # Capteur indisponible : on ne tranche pas, on laisse l'état courant.
                return self._applied.get(clim, off_state)
            if solar > s.seuil_haute:
                return on_state(COMPUTED_CONFORT, s.temp_confort)
            if solar >= s.seuil_basse:
                return on_state(COMPUTED_ECO, s.temp_eco)
            return off_state

        # 0. Mode « solaire uniquement » : on ignore mois/horaire/Tempo et on
        # n'applique que l'asservissement solaire, en continu, 24h/24.
        if s.solar_only:
            return solar_state()

        # 1. Mois désactivé -> off.
        if now.month not in zone.active_months:
            return off_state

        tempo = self._get_tempo()
        current = now.time()

        # 2. Plage horaire. Le début dépend de la couleur Tempo.
        start = s.heure_start_rouge if tempo == TEMPO_ROUGE else s.heure_start_normal
        if current < start:
            return off_state
        sunset_stop = self._sunset_stop(now, s.decalage_coucher)
        if sunset_stop is not None and now >= sunset_stop:
            return off_state

        # 3. Jour rouge, fenêtre matinale -> préchauffe ÉCO forcée.
        if tempo == TEMPO_ROUGE and current < s.heure_stop_rouge_matin:
            return on_state(COMPUTED_PRECHAUFFE_ROUGE, s.temp_eco)

        # 4. Asservissement solaire (seuils propres à la zone).
        return solar_state()

    def compute_desired(
        self, zone: ZoneConfig, clim: str, now: datetime, zone_active: bool
    ) -> DesiredState:
        """Calcule l'état désiré d'une clim.

        Le hors-gel est un *plancher* : il ne fait jamais baisser une consigne
        déjà plus haute, et reste actif même si la zone ou la clim est
        désactivée manuellement (sécurité du logement avant tout).
        """
        s = self.settings[zone.key]
        clim_active = self.clim_enabled.get(clim, True)

        room_temp = self._get_zone_temperature(zone)
        hors_gel_triggered = room_temp is not None and room_temp < s.hors_gel

        disabled = not clim_active or not zone_active
        base = (
            DesiredState(computed=COMPUTED_DISABLED, hvac_mode=HVAC_OFF)
            if disabled
            else self._compute_base(zone, clim, now)
        )

        if not hors_gel_triggered:
            return base

        if base.is_on and base.temperature is not None and base.temperature >= s.hors_gel:
            # La consigne normale couvre déjà le plancher hors-gel.
            return base

        return DesiredState(
            computed=COMPUTED_HORS_GEL,
            hvac_mode=s.hvac_mode,
            temperature=s.hors_gel,
            fan_mode=s.fan_mode,
            flux_horizontal=s.flux_horizontal,
            flux_vertical=s.flux_vertical,
        )

    # ----------------------------------------------------------- application
    async def _async_update_data(self) -> dict[str, DesiredState]:
        """Recalcule et applique l'état désiré de toutes les clims."""
        now = dt_util.now()
        result: dict[str, DesiredState] = {}

        for zone in self.zones.values():
            zone_active = self.settings[zone.key].active
            for clim in zone.climates:
                desired = self.compute_desired(zone, clim, now, zone_active)
                result[clim] = desired
                await self._async_apply(zone, clim, desired)

        return result

    def _is_on(self, clim: str) -> bool:
        """Vrai si la clim est actuellement allumée (état HA réel)."""
        state = self.hass.states.get(clim)
        return state is not None and state.state not in _OFF_STATES

    @staticmethod
    def _clamp_temperature(desired: DesiredState) -> DesiredState:
        """Borne toute consigne envoyée à la clim à sa valeur minimale physique."""
        if (
            desired.temperature is not None
            and desired.temperature < DEVICE_MIN_TEMP_SETPOINT
        ):
            return replace(desired, temperature=DEVICE_MIN_TEMP_SETPOINT)
        return desired

    def _court_cycle_locked(self, clim: str, now: datetime) -> bool:
        """Vrai si un changement ON/OFF est verrouillé par l'anti-court-cycle."""
        last = self._last_onoff_change.get(clim)
        if last is None:
            return False
        window = timedelta(minutes=self.anti_court_cycle_minutes)
        return (now - last) < window

    async def _async_apply(
        self, zone: ZoneConfig, clim: str, desired: DesiredState
    ) -> None:
        """Fait converger une clim vers l'état désiré (avec sécurités)."""
        desired = self._clamp_temperature(desired)
        now = dt_util.now()
        currently_on = self._is_on(clim)

        # --- Anti-court-cycle : on ne bascule ON<->OFF qu'après le délai. ---
        if desired.is_on != currently_on and self._court_cycle_locked(clim, now):
            _LOGGER.debug(
                "Anti-court-cycle actif pour %s, bascule différée", clim
            )
            return

        if not desired.is_on:
            if currently_on:
                await self._call_hvac_mode(clim, HVAC_OFF)
                self._last_onoff_change[clim] = now
                self._schedule_verify(clim, HVAC_OFF)
            self._applied[clim] = desired
            return

        # --- Allumage / mise à jour des paramètres ---
        applied = self._applied.get(clim)

        if not currently_on:
            self._last_onoff_change[clim] = now

        # hvac_mode
        if desired.hvac_mode != self._current_hvac(clim):
            await self._call_hvac_mode(clim, desired.hvac_mode)
            self._schedule_verify(clim, desired.hvac_mode)

        # temperature
        if desired.temperature is not None and (
            applied is None or applied.temperature != desired.temperature
        ):
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: clim, "temperature": desired.temperature},
                blocking=True,
            )

        # fan_mode
        if desired.fan_mode is not None and (
            applied is None or applied.fan_mode != desired.fan_mode
        ):
            await self.hass.services.async_call(
                "climate",
                "set_fan_mode",
                {ATTR_ENTITY_ID: clim, "fan_mode": desired.fan_mode},
                blocking=True,
            )

        # flux horizontal / vertical (entités select)
        await self._apply_flux(zone.flux_h_map.get(clim), desired.flux_horizontal)
        await self._apply_flux(zone.flux_v_map.get(clim), desired.flux_vertical)

        self._applied[clim] = desired

    async def _apply_flux(self, select_entity: str | None, option: str | None) -> None:
        """Applique une option de flux si différente de l'état courant."""
        if not select_entity or not option:
            return
        state = self.hass.states.get(select_entity)
        if state is not None and state.state == option:
            return
        await self.hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: select_entity, "option": option},
            blocking=True,
        )

    def _current_hvac(self, clim: str) -> str | None:
        """Mode HVAC courant de la clim."""
        state = self.hass.states.get(clim)
        return state.state if state else None

    async def _call_hvac_mode(self, clim: str, hvac_mode: str) -> None:
        """Envoie un changement de hvac_mode."""
        await self.hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: clim, "hvac_mode": hvac_mode},
            blocking=True,
        )

    @callback
    def _schedule_verify(self, clim: str, expected_hvac: str) -> None:
        """Vérifie après un court délai que la commande hvac a bien été appliquée.

        Certaines clims (intégrations cloud) ignorent ou retardent des ordres ;
        on retente une fois et on journalise si l'état attendu n'est pas atteint.
        """

        async def _verify(_now: datetime) -> None:
            current = self._current_hvac(clim)
            expected_on = expected_hvac != HVAC_OFF
            current_on = current not in _OFF_STATES
            if expected_on != current_on:
                _LOGGER.warning(
                    "%s n'a pas appliqué hvac_mode=%s (état=%s), nouvelle tentative",
                    clim,
                    expected_hvac,
                    current,
                )
                await self._call_hvac_mode(clim, expected_hvac)

        async_call_later(self.hass, COMMAND_VERIFY_DELAY_SECONDS, _verify)
