"""Constantes pour l'intégration Climate Automation."""

from __future__ import annotations

from datetime import time
from typing import Final

DOMAIN: Final = "climate_automation"

# --- Réévaluation périodique du moteur ---------------------------------------
# Le moteur recalcule l'état désiré de chaque clim à cet intervalle. C'est le
# filet de sécurité qui remplace les déclencheurs horaires fragiles de l'ancien
# YAML : entre l'heure de début et de fin, on vérifie en continu que chaque clim
# est dans le bon état.
UPDATE_INTERVAL_SECONDS: Final = 300  # 5 minutes

# Debounce appliqué aux variations du capteur de production solaire.
SOLAR_DEBOUNCE_SECONDS: Final = 30

# Délai après une commande avant de vérifier qu'elle a bien été appliquée.
COMMAND_VERIFY_DELAY_SECONDS: Final = 20

# --- Nombre de zones ----------------------------------------------------------
NUM_ZONES: Final = 3
ZONE_KEYS: Final = ["zone_1", "zone_2", "zone_3"]

# --- Clés de configuration globale (config entry data) -----------------------
CONF_SOLAR_SENSOR: Final = "solar_sensor"
CONF_TEMPO_SENSOR: Final = "tempo_sensor"
CONF_ZONES: Final = "zones"

# --- Clés de configuration par zone (structurel, config/options flow) --------
CONF_ZONE_NAME: Final = "name"
CONF_ZONE_CLIMATES: Final = "climates"
CONF_ZONE_TEMP_SENSOR: Final = "temp_sensor"
CONF_ZONE_FLUX_H_MAP: Final = "flux_h_map"  # {climate_entity: select_entity}
CONF_ZONE_FLUX_V_MAP: Final = "flux_v_map"  # {climate_entity: select_entity}

# --- Mois (libellés FR, utilisés pour les interrupteurs « mois actif ») ------
MONTH_LABELS: Final = (
    (1, "Janvier"),
    (2, "Février"),
    (3, "Mars"),
    (4, "Avril"),
    (5, "Mai"),
    (6, "Juin"),
    (7, "Juillet"),
    (8, "Août"),
    (9, "Septembre"),
    (10, "Octobre"),
    (11, "Novembre"),
    (12, "Décembre"),
)

# --- Couleur Tempo ------------------------------------------------------------
TEMPO_ROUGE: Final = "rouge"

# --- Modes HVAC sélectionnables ----------------------------------------------
HVAC_MODE_OPTIONS: Final = ["heat", "cool", "dry", "fan_only", "auto"]
DEFAULT_HVAC_MODE: Final = "heat"

# Modes HVAC considérés comme « allumés » (pour décider d'une extinction).
HVAC_ON_STATES: Final = ["heat", "cool", "dry", "fan_only", "auto", "heat_cool"]
HVAC_OFF: Final = "off"

# --- Modes de ventilation sélectionnables ------------------------------------
FAN_MODE_OPTIONS: Final = ["auto", "low", "medium", "high", "quiet"]
DEFAULT_FAN_MODE: Final = "auto"

# --- Valeurs par défaut des réglages (number / time) -------------------------
DEFAULT_TEMP_CONFORT: Final = 24.0
DEFAULT_TEMP_ECO: Final = 19.0
DEFAULT_SEUIL_HAUTE: Final = 1.2  # kW
DEFAULT_SEUIL_BASSE: Final = 1.0  # kW
DEFAULT_HORS_GEL: Final = 10.0  # °C
DEFAULT_ANTI_COURT_CYCLE_MINUTES: Final = 5.0

DEFAULT_HEURE_START_ROUGE: Final = time(6, 0)
DEFAULT_HEURE_START_NORMAL: Final = time(7, 0)
DEFAULT_HEURE_STOP_ROUGE_MATIN: Final = time(9, 0)
# Décalage (minutes) par rapport au coucher du soleil : négatif = arrêt avant
# le coucher, positif = arrêt après le coucher (utile en hiver pour prolonger
# le chauffage une fois la nuit tombée).
DEFAULT_DECALAGE_COUCHER: Final = -30.0

# Consigne minimale physiquement acceptée par les climatiseurs. Toute commande
# de température envoyée à une clim est bornée à cette valeur, quelle que soit
# la consigne calculée (confort, éco ou hors-gel).
DEVICE_MIN_TEMP_SETPOINT: Final = 16.0

# Bornes des entités number.
MIN_TEMP: Final = DEVICE_MIN_TEMP_SETPOINT
MAX_TEMP: Final = 30.0
TEMP_STEP: Final = 0.5
# Le seuil hors-gel est comparé à un capteur de température réelle (pas envoyé
# à la clim) : il peut donc être réglé sous la consigne minimale des appareils.
MIN_HORS_GEL_THRESHOLD: Final = 0.0
MAX_HORS_GEL_THRESHOLD: Final = 20.0
MIN_SEUIL: Final = 0.0
MAX_SEUIL: Final = 20.0
SEUIL_STEP: Final = 0.1
MIN_ANTI_COURT_CYCLE: Final = 0.0
MAX_ANTI_COURT_CYCLE: Final = 60.0
MIN_DECALAGE_COUCHER: Final = -240.0
MAX_DECALAGE_COUCHER: Final = 240.0
DECALAGE_COUCHER_STEP: Final = 5.0

# --- Identifiants des réglages « live » par zone -----------------------------
# (utilisés pour construire les unique_id et le stockage runtime)
SETTING_ACTIVE: Final = "active"
SETTING_SOLAR_ONLY: Final = "solar_only"
SETTING_TEMP_CONFORT: Final = "temp_confort"
SETTING_TEMP_ECO: Final = "temp_eco"
SETTING_SEUIL_HAUTE: Final = "seuil_haute"
SETTING_SEUIL_BASSE: Final = "seuil_basse"
SETTING_HORS_GEL: Final = "hors_gel"
SETTING_HVAC_MODE: Final = "hvac_mode"
SETTING_FAN_MODE: Final = "fan_mode"
SETTING_FLUX_H: Final = "flux_horizontal"
SETTING_FLUX_V: Final = "flux_vertical"
SETTING_START_ROUGE: Final = "heure_start_rouge"
SETTING_START_NORMAL: Final = "heure_start_normal"
SETTING_STOP_ROUGE_MATIN: Final = "heure_stop_rouge_matin"
SETTING_DECALAGE_COUCHER: Final = "decalage_coucher"

# Réglages globaux (un seul réglage pour les 3 zones).
SETTING_ANTI_COURT_CYCLE: Final = "anti_court_cycle"
SETTING_MONTH_PREFIX: Final = "month_active_"

# --- États calculés (diagnostic) ---------------------------------------------
COMPUTED_OFF: Final = "off"
COMPUTED_CONFORT: Final = "confort"
COMPUTED_ECO: Final = "eco"
COMPUTED_HORS_GEL: Final = "hors_gel"
COMPUTED_PRECHAUFFE_ROUGE: Final = "prechauffe_rouge"
COMPUTED_DISABLED: Final = "disabled"
