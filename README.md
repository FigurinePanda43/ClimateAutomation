# Climate Automation

Intégration Home Assistant (installable via HACS) qui remplace l'automatisation
YAML *« Chauffage multi-zones programmé - Gestion Tempo et production solaire »*
par une logique en Python, plus fiable et entièrement configurable depuis
l'interface.

Voir [`DESIGN.md`](DESIGN.md) pour l'architecture détaillée et
[`original_automation`](original_automation) pour l'automatisation d'origine.

## Fonctionnement

Pour chaque **zone** (3 zones indépendantes) et chaque **climatiseur** activé,
le moteur calcule en continu l'état désiré selon, par ordre de priorité :

1. **Hors-gel** (capteur de température réel, repli sur la zone 1) — prioritaire.
2. **Mois désactivé** → extinction.
3. **Hors plage horaire** (avant le début / après coucher du soleil − décalage) → extinction.
4. **Jour Tempo rouge, fenêtre matinale** → préchauffe en éco.
5. **Asservissement solaire** (seuils propres à la zone) :
   production haute → confort, moyenne → éco, basse → extinction.

## Sécurités

- **Anti-court-cycle** : délai minimum (défaut 5 min) entre deux bascules ON/OFF.
- **Hors-gel** par capteur réel (défaut 10 °C).
- **Vérification de commande appliquée** avec nouvelle tentative.
- **Debounce solaire** pour éviter le flapping autour des seuils.

## Installation (HACS)

1. HACS → Intégrations → menu → *Dépôts personnalisés*.
2. Ajouter `https://github.com/FigurinePanda43/ClimateAutomation` (catégorie *Intégration*).
3. Installer « Climate Automation », redémarrer Home Assistant.
4. Paramètres → Appareils et services → *Ajouter une intégration* → Climate Automation.

## Configuration

À l'ajout : capteurs globaux (production solaire, couleur Tempo), puis pour
chaque zone : nom, climatiseurs, capteur de température, mois actifs, et le
mapping des entités de flux d'air.

Les réglages courants (températures confort/éco, seuils solaires, horaires,
modes, hors-gel, activation zone/clim) sont exposés comme **entités**
(`number`, `select`, `time`, `switch`) modifiables en direct.
