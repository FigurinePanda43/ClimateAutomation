"""Modèles de données pour Climate Automation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

from .const import (
    CONF_ZONE_CLIMATES,
    CONF_ZONE_FLUX_H_MAP,
    CONF_ZONE_FLUX_V_MAP,
    CONF_ZONE_NAME,
    CONF_ZONE_TEMP_SENSOR,
    DEFAULT_DECALAGE_COUCHER,
    DEFAULT_FAN_MODE,
    DEFAULT_HEURE_START_NORMAL,
    DEFAULT_HEURE_START_ROUGE,
    DEFAULT_HEURE_STOP_ROUGE_MATIN,
    DEFAULT_HORS_GEL,
    DEFAULT_HVAC_MODE,
    DEFAULT_SEUIL_BASSE,
    DEFAULT_SEUIL_HAUTE,
    DEFAULT_TEMP_CONFORT,
    DEFAULT_TEMP_ECO,
)


@dataclass
class ZoneConfig:
    """Configuration structurelle d'une zone (issue du config/options flow).

    Ces champs décrivent *quelles* entités composent la zone ; les valeurs
    ajustables en direct (températures, seuils, horaires, modes…) sont stockées
    séparément dans :class:`ZoneSettings`.
    """

    key: str
    name: str
    climates: list[str] = field(default_factory=list)
    temp_sensor: str | None = None
    # Mapping climate_entity -> select_entity de flux.
    flux_h_map: dict[str, str] = field(default_factory=dict)
    flux_v_map: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, key: str, data: dict) -> "ZoneConfig":
        """Construit une ZoneConfig depuis le dict stocké dans la config entry."""
        return cls(
            key=key,
            name=data.get(CONF_ZONE_NAME, key),
            climates=list(data.get(CONF_ZONE_CLIMATES, [])),
            temp_sensor=data.get(CONF_ZONE_TEMP_SENSOR) or None,
            flux_h_map=dict(data.get(CONF_ZONE_FLUX_H_MAP, {})),
            flux_v_map=dict(data.get(CONF_ZONE_FLUX_V_MAP, {})),
        )


@dataclass
class ZoneSettings:
    """Valeurs ajustables en direct d'une zone (entités number/select/time/switch).

    Les valeurs par défaut servent à l'initialisation ; elles sont ensuite
    pilotées par l'utilisateur via les entités créées par l'intégration.
    """

    active: bool = True
    solar_only: bool = False
    manual: bool = False
    temp_confort: float = DEFAULT_TEMP_CONFORT
    temp_eco: float = DEFAULT_TEMP_ECO
    seuil_haute: float = DEFAULT_SEUIL_HAUTE
    seuil_basse: float = DEFAULT_SEUIL_BASSE
    heure_start_normal: time = DEFAULT_HEURE_START_NORMAL
    # Minutes par rapport au coucher du soleil (négatif = avant, positif = après).
    decalage_coucher: float = DEFAULT_DECALAGE_COUCHER


@dataclass
class GlobalSettings:
    """Réglages communs aux 3 zones, pilotés depuis l'appareil principal.

    Contrairement à :class:`ZoneSettings`, ces valeurs ne sont pas dupliquées
    par zone : une seule entité commande les 3 zones à la fois.
    """

    hvac_mode: str = DEFAULT_HVAC_MODE
    fan_mode: str = DEFAULT_FAN_MODE
    flux_horizontal: str | None = None
    flux_vertical: str | None = None
    hors_gel: float = DEFAULT_HORS_GEL
    heure_start_rouge: time = DEFAULT_HEURE_START_ROUGE
    heure_stop_rouge_matin: time = DEFAULT_HEURE_STOP_ROUGE_MATIN
    # Mois (1..12) où le chauffage est autorisé, communs aux 3 zones.
    active_months: set[int] = field(default_factory=lambda: set(range(1, 13)))


@dataclass
class DesiredState:
    """État désiré calculé pour une clim donnée."""

    # Mode calculé (pour le diagnostic) : confort / eco / off / hors_gel / ...
    computed: str
    hvac_mode: str  # "off" ou un mode HVAC réel
    temperature: float | None = None
    fan_mode: str | None = None
    flux_horizontal: str | None = None
    flux_vertical: str | None = None
    # Faux si l'automatisation ne doit envoyer aucune commande (mode manuel, ou
    # en pleine nuit au-delà de la marge de transition) : la clim est laissée
    # entièrement à la main de l'utilisateur.
    managed: bool = True

    @property
    def is_on(self) -> bool:
        """Vrai si l'état désiré demande la clim allumée."""
        return self.hvac_mode != "off"
