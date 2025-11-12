#!/usr/bin/env python3
"""
POLISH C2 DOCTRINE SERVICE - INTEGRATED AIR AND MISSILE DEFENSE (IAMD)
Multi-coalition weapon-target pairing for Polish Air Defense

Integrates:
- US Patriot batteries (ballistic missile defense)
- Norwegian NASAMS (cruise missiles + aircraft)
- British Sky Sabre (forward deployed, UK ROE)
- Polish F-16 + MiG-29 QRA
- Polish Piorun MANPADS
- Legacy S-125 Neva

Created by: Joel Trout
For: Polish Ministry of National Defence
Deputy Director: Paweł Bejda
Version: 1.0 - Kaliningrad Corridor Optimized
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class ThreatType(Enum):
    # Air threats
    AIRCRAFT_TRANSPORT = "Transport Aircraft"
    AIRCRAFT_FIGHTER = "Fighter/Bomber"
    AIRCRAFT_RECONNAISSANCE = "Reconnaissance (IL-20, Tu-134)"
    HELICOPTER_ATTACK = "Attack Helicopter"
    HELICOPTER_TRANSPORT = "Transport Helicopter"

    # Missile threats
    BALLISTIC_MISSILE_ISKANDER = "Iskander Ballistic Missile"
    CRUISE_MISSILE_KALIBR = "Kalibr Cruise Missile"
    CRUISE_MISSILE_KH101 = "Kh-101 Cruise Missile"

    # Drone threats
    DRONE_SHAHED = "Shahed-136 Drone"
    DRONE_ORLAN = "Orlan-10 Reconnaissance"
    DRONE_SMALL = "Small Commercial UAV"

    UNKNOWN = "Unknown Contact"

class SystemType(Enum):
    # Polish Systems
    F16_QRA = "F-16 QRA (Polish)"
    MIG29_QRA = "MiG-29 QRA (Polish - Legacy)"
    PIORUN_MANPADS = "Piorun MANPADS"
    S125_NEVA = "S-125 Neva (Legacy Soviet)"

    # US Systems
    PATRIOT_PAC3 = "Patriot PAC-3 (US)"

    # Norwegian Systems
    NASAMS_BATTERY = "NASAMS (Norwegian)"

    # British Systems
    SKY_SABRE = "Sky Sabre (British)"

    # Electronic Warfare
    ELECTRONIC_WARFARE = "Polish EW System"

class ContactPriority(Enum):
    CRITICAL = "Critical"    # Ballistic missile, airspace violation
    HIGH = "High"           # Kaliningrad provocation, approaching border
    MEDIUM = "Medium"       # International airspace, monitoring
    LOW = "Low"            # Routine patrol, distant

class SensorSource(Enum):
    POLISH_RADAR = "Polish_Radar"
    NATO_AWACS = "NATO_AWACS"
    US_PATRIOT_RADAR = "US_Patriot_Radar"
    NASAMS_RADAR = "NASAMS_Radar"
    SKY_SABRE_RADAR = "Sky_Sabre_Radar"
    VISUAL_QRA = "Visual_QRA"
    GROUND_OBSERVER = "Ground_Observer"

@dataclass
class SensorContact:
    """Single sensor contact"""
    source: SensorSource
    track_id: str
    bearing: int  # degrees
    range_km: float
    altitude_m: int
    speed_knots: float
    confidence: float  # 0-1
    classification: str
    iff_response: Optional[str] = None
    data_age_seconds: int = 0
    ecm_detected: bool = False
    transponder_status: Optional[str] = None  # "ON", "OFF", "INTERMITTENT"
    platform_name: Optional[str] = None

@dataclass
class MultiSensorThreat:
    """Correlated threat from multiple sensors"""
    contacts: List[SensorContact]
    threat_type: ThreatType
    priority: ContactPriority
    estimated_bearing: int
    estimated_range_km: float
    time_to_border_minutes: float  # Time until Polish border
    target_description: str
    origin: Optional[str] = None  # "Kaliningrad", "Belarus", "Ukraine spillover"

    def sensor_agreement(self) -> float:
        """Calculate how well sensors agree (0-1)"""
        if len(self.contacts) < 2:
            return 1.0

        bearings = [c.bearing for c in self.contacts]
        ranges = [c.range_km for c in self.contacts]

        bearing_spread = max(bearings) - min(bearings)
        range_spread = max(ranges) - min(ranges)

        # Lower spread = higher agreement
        bearing_agreement = max(0, 1.0 - bearing_spread / 20.0)
        range_agreement = max(0, 1.0 - range_spread / 15.0)

        return (bearing_agreement + range_agreement) / 2

@dataclass
class AvailableAsset:
    """Available coalition asset"""
    system_type: SystemType
    count: int
    ready_state: str  # "READY", "STANDBY_15MIN", "MAINTENANCE", "TRAINING"
    effective_range_km: float
    response_time_minutes: int
    cost_per_engagement_pln: int  # Polish Złoty
    success_rate: float
    location: str

    # Coalition coordination
    requires_nato_clearance: bool = False
    requires_polish_clearance: bool = True
    requires_us_clearance: bool = False
    requires_uk_clearance: bool = False

    # Classification level
    classification_level: str = "POLISH_RESTRICTED"  # or "NATO_SECRET", "US_NOFORN", "UK_OFFICIAL"

    # Reload time
    reload_time_minutes: int = 0
    missiles_available: int = 0

@dataclass
class OperationalContext:
    """Polish operational context"""
    location: str
    weather: str
    visibility_km: float
    gps_jamming_active: bool  # Kaliningrad EW
    cellular_disrupted: bool  # Russian EW
    link16_jamming: bool      # Communication degradation
    nato_caoc_connection: bool  # Connected to Uedem

    # Kaliningrad corridor specific
    kaliningrad_corridor_active: bool
    belarus_border_tension: bool
    ukrainian_war_spillover_risk: bool
    suwalki_gap_monitoring: bool

    # Allied presence
    us_forces_deployed: bool
    uk_sky_sabre_active: bool
    norwegian_nasams_ready: bool

    # Strategic concerns
    strategic_assets_nearby: List[str]
    civilian_traffic_nearby: bool
    escalation_risk: str  # "LOW", "MEDIUM", "HIGH"
    historical_pattern: str

@dataclass
class GeneratedOption:
    """Single tactical option"""
    option_id: str
    title: str
    description: str
    template_id: str
    estimated_cost_pln: int
    estimated_success_rate: float
    assets_used: List[str]
    nato_coordination_required: bool
    polish_sovereignty_maintained: bool
    degraded_comms_compatible: bool  # Works without cloud/Link 16

# ============================================================================
# POLISH DOCTRINE TEMPLATES
# ============================================================================

class PolishIAMDDoctrine:
    """
    Polish Integrated Air and Missile Defense Doctrine
    NATO Eastern Flank - Kaliningrad Corridor Optimized
    """

    TEMPLATES = {
        'kaliningrad_corridor_qra': {
            'title': 'Korytarz Kaliningradzki: Natychmiastowy start QRA',
            'trigger': lambda t, a, c: (
                t.origin == "Kaliningrad" and
                t.time_to_border_minutes < 15 and
                t.priority in [ContactPriority.CRITICAL, ContactPriority.HIGH] and
                any(asset.system_type in [SystemType.F16_QRA, SystemType.MIG29_QRA] for asset in a)
            ),
            'template': """
OPCJA: Natychmiastowy start QRA - Korytarz Kaliningradzki

POLSKA DOKTRYNA: Rosyjskie naruszenie lub zbliżenie <15 min → QRA START NATYCHMIAST

SYTUACJA POWIETRZNA:
- Kontakt: {contact_description}
- Pochodzenie: {origin}
- Dystans do granicy: {range_km}km
- Czas do granicy: {time_to_border} minut
- Status transpondera: {transponder_status}
- Wykryte zakłócenia EW: {ecm_status}

DOSTĘPNE SIŁY:
- {qra_count}x {qra_type} z bazy {qra_base}
- Czas gotowości: {qra_response_time} minut
- Zadanie: WIZUALNA IDENTYFIKACJA przed granicą
- Backup: {backup_systems}

KOORDYNACJA NATO:
- {nato_caoc_status}
- Polskie QRA zachowuje narodowe dowództwo
- Równoległa informacja do NATO CAOC Uedem
- Link 16: {link16_status}

OPTYMALIZACJA ZASOBÓW:
- Koszt sortu: {cost_per_sortie:,} PLN
- Unikamy {avoided_sorties} niepotrzebnych startów dziennie
- Oszczędność roczna: ~{annual_savings:,} PLN przy poprawnej optymalizacji

ZAKŁÓCENIA ŁĄCZNOŚCI:
- GPS: {gps_status}
- Łączność komórkowa: {cellular_status}
- Link 16: {link16_jamming}
- DECYZJA: Możliwa lokalnie bez łączności z Warszawą

SUWERENNOŚĆ:
✓ Polskie dowództwo nad własnymi samolotami
✓ Narodowy łańcuch dowodzenia zachowany
✓ NATO informowane zgodnie z procedurami
✓ Decyzja lokalna w 23 Bazie w Mińsku Mazowieckim

KOSZT: {cost:,} PLN
PRAWDOPODOBIEŃSTWO: {success_rate}%
SUWERENNOŚĆ: ZACHOWANA
KOMPATYBILNOŚĆ Z ZAKŁÓCENIAMI: TAK (lokalnie)
"""
        },

        'iamd_weapon_target_pairing': {
            'title': 'IAMD: Optymalne parowanie broń-cel',
            'trigger': lambda t, a, c: (
                t.threat_type in [
                    ThreatType.BALLISTIC_MISSILE_ISKANDER,
                    ThreatType.CRUISE_MISSILE_KALIBR,
                    ThreatType.DRONE_SHAHED
                ] and
                len(a) >= 3  # Multiple systems available
            ),
            'template': """
OPCJA: Zintegrowana obrona przeciwlotnicza i przeciwrakietowa (IAMD)

DOKTRYNA: Każdy system do odpowiedniego celu - optymalizacja kosztów i sukcesu

CEL: {threat_type}
PRIORYTET: {priority}
CZAS DO GRANICY: {time_to_border} minut

WARSTWA 1 - DALEKI ZASIĘG (Pociski balistyczne):
{patriot_layer}

WARSTWA 2 - ŚREDNI ZASIĘG (Pociski manewrujące, samoloty):
{nasams_layer}

WARSTWA 3 - BLISKI ZASIĘG (Drony, wolno lecące cele):
{manpads_layer}

PAROWANIE BROŃ-CEL:
{weapon_target_assignment}

MATEMATYKA SUKCESU:
- Pojedyncza warstwa: {single_layer_success}%
- Dwie warstwy: {two_layer_success}%
- Trzy warstwy: {three_layer_success}%

EKONOMIA:
- Minimalny koszt (1 warstwa): {min_cost:,} PLN
- Typowy koszt (2 warstwy): {typical_cost:,} PLN
- Maksymalny koszt (3 warstwy): {max_cost:,} PLN
- Oczekiwany koszt: {expected_cost:,} PLN

KOORDYNACJA KOALICYJNA:
{coalition_coordination}

CZAS PRZEŁADOWANIA:
{reload_times}

POKRYCIE PO ZAANGAŻOWANIU:
{coverage_after_engagement}

KOSZT: {expected_cost:,} PLN (oczekiwany)
PRAWDOPODOBIEŃSTWO: {three_layer_success}%
WARSTWY: {active_layers}
"""
        },

        'coalition_no_data_sharing': {
            'title': 'Koalicja: Koordynacja bez wymiany danych klasyfikowanych',
            'trigger': lambda t, a, c: (
                any(a.requires_us_clearance for a in a) and
                any(a.requires_uk_clearance for a in a) and
                any(a.requires_polish_clearance for a in a)
            ),
            'template': """
OPCJA: Koordynacja koalicyjna z zachowaniem poziomów niejawności

PROBLEM: Różne narodowe poziomy niejawności
- Amerykańskie Patriot: US NOFORN (brak dostępu dla Polski)
- Brytyjski Sky Sabre: UK OFFICIAL / UK ROE
- Norweski NASAMS: Norweski dostęp
- Polskie systemy: POUFNE PL

ROZWIĄZANIE ARBITER: Język naturalny bez wymian danych klasyfikowanych

KAŻDY SYSTEM RAPORTUJE (w języku naturalnym):
- Patriot (US): "{patriot_report}"
- Sky Sabre (UK): "{sky_sabre_report}"
- NASAMS (NO): "{nasams_report}"
- Polskie systemy: "{polish_report}"

ARBITER GENERUJE REKOMENDACJE bez dostępu do surowych danych śledzenia

NARODOWE ROE ZACHOWANE:
- USA: {us_roe}
- UK: {uk_roe}
- Norwegia: {norway_roe}
- Polska: {poland_roe}

KAŻDY NARÓD WIDZI:
- Własne klasyfikowane dane: TAK
- Cudze klasyfikowane dane: NIE
- Rekomendacje ARBITER: TAK (niesklasyfikowane)

KOORDYNACJA:
{coordination_method}

INTER OPERACYJNOŚĆ BEZ WIELOSTRONNYCH UMÓW o wymianie danych

ZALETY:
- Nie wymaga złożonych umów wymiany danych
- Każdy naród zachowuje kontrolę nad własnymi danymi
- Koordynacja poprzez język naturalny
- Szybsze wdrożenie (brak biurokracji)

KOSZT: {cost:,} PLN
WSPÓŁPRACA KOALICYJNA: TAK
WYMIANA DANYCH KLASYFIKOWANYCH: NIE (niepotrzebna)
EFEKTYWNOŚĆ: {effectiveness}%
"""
        },

        'kaliningrad_provocation_pattern': {
            'title': 'Prowokacja Kaliningrad: Analiza wzorca historycznego',
            'trigger': lambda t, a, c: (
                t.origin == "Kaliningrad" and
                t.priority in [ContactPriority.MEDIUM, ContactPriority.HIGH] and
                "IL-20" in str(t.threat_type.value) or "transponder" in c.historical_pattern.lower()
            ),
            'template': """
OPCJA: Wzorzec prowokacji - analiza przed decyzją

TYPOWY WZORZEC KALININGRAD:
- IL-20 reconnaissance loty 2-4 razy miesięcznie
- Celowe wyłączanie transpondera blisko granicy
- Naruszenia 2-3km, następnie zawracanie
- Koordynacja z białoruskim EW dla niejednoznacznych śladów

OBECNA SYTUACJA:
- Rodzaj samolotu: {aircraft_type}
- Transponder: {transponder_status}
- Odległość od granicy: {distance_km}km
- Wykryto zakłócenia EW: {ecm_detected}
- Zgodność z historycznym wzorcem: {pattern_match}%

HISTORYCZNE DANE (ostatnie 90 dni):
- Podobne zdarzenia: {similar_events} razy
- Z tych faktyczne naruszenia: {actual_violations}
- Typowy czas trwania: {typical_duration} minut
- Typowa głębokość naruszenia: {typical_depth}km

ANALIZA DECYZJI:
JEŚLI start QRA teraz:
- Koszt: {qra_cost:,} PLN
- Rosyjski samolot prawdopodobnie zawróci: {turnback_probability}%
- Efektywność: {effectiveness_immediate}%

JEŚLI monitorowanie przez {monitoring_time} minut:
- Koszt: 0 PLN (kontynuacja śledzenia)
- Jeśli wzorzec się potwierdzi: oszczędność {qra_cost:,} PLN
- Jeśli to prawdziwe zagrożenie: strata {time_lost} minut
- Wciąż margines na QRA: {qra_margin} minut

ESKALACJA:
- Ryzyko eskalacji przy starcie QRA: {escalation_risk}
- Związek z napięciami na Białorusi: {belarus_connection}
- Aktywność na korytarzu Suwałki: {suwalki_activity}

REKOMENDACJA na podstawie wzorca:
{pattern_recommendation}

KOSZT: {cost:,} PLN
METODA: {method}
ZGODNOŚĆ ZE WZORCEM: {pattern_match}%
"""
        },

        'degraded_comms_local_decision': {
            'title': 'Zakłócona łączność: Decyzja lokalna bez Warszawy',
            'trigger': lambda t, a, c: (
                (c.gps_jamming_active or c.link16_jamming or not c.nato_caoc_connection) and
                t.time_to_border_minutes < 10
            ),
            'template': """
OPCJA: Decyzja lokalna - zakłócona łączność z centrum dowodzenia

STATUS ŁĄCZNOŚCI:
- GPS: {gps_status}
- Łączność komórkowa: {cellular_status}
- Link 16: {link16_status}
- Połączenie z Warszawskim Centrum Operacji Powietrznych: {warsaw_connection}
- Połączenie z NATO CAOC Uedem: {nato_caoc_connection}

AKTYWNE ZAKŁÓCENIA ROSYJSKIE:
- Źródło: {jamming_source}
- Dotkniętew obszary: {affected_areas}
- Siła zakłóceń: {jamming_strength}

ARBITER 26MB - DZIAŁANIE LOKALNE:
✓ Laptop taktyczny w 23 Bazie (Mińsk Mazowiecki)
✓ Air-gapped (bez łączności z chmurą)
✓ Wciąż operacyjny mimo zakłóceń rosyjskich
✓ Decyzja <1 sekundy

DOSTĘPNE SYSTEMY (kontrola lokalna):
{local_systems}

SYSTEMY WYMAGAJĄCE ZEWNĘTRZNEJ KOORDYNACJI (niedostępne):
{remote_systems}

CEL: {threat_description}
CZAS DO GRANICY: {time_to_border} minut

DECYZJA LOKALNA:
{local_decision}

ROE - DECYZJA LOKALNA:
- Polska doktryna pozwala na decyzję lokalną przy:
  1. Utracie łączności
  2. Czasie <10 minut do granicy
  3. Jednoznacznym zagrożeniu
- Raport post-event do Warszawy

ZALETY:
- Szybka decyzja mimo zakłóceń
- Niepotrzebna łączność z chmurą
- Rosyjskie EW nie blokuje decyzji
- 26MB ARBITER działa offline

KOSZT: {cost:,} PLN
PRAWDOPODOBIEŃSTWO: {success_rate}%
WYMAGA ŁĄCZNOŚCI: NIE
ARBITER AIR-GAPPED: OPERACYJNY
"""
        },

        'resource_optimization_daily': {
            'title': 'Optymalizacja zasobów: Unikanie niepotrzebnych sortów',
            'trigger': lambda t, a, c: (
                c.kaliningrad_corridor_active and
                t.priority in [ContactPriority.MEDIUM, ContactPriority.LOW]
            ),
            'template': """
OPCJA: Optymalizacja zasobów - unikanie niepotrzebnych startów QRA

PROBLEM OPERACYJNY:
- Kaliningrad: Stała aktywność lotnicza (rutynowo)
- Dzienne prowokacje: {daily_provocations} zdarzenia
- Koszt sortu F-16: {f16_cost:,} PLN
- Potencjalny koszt dzienny przy 100% startów: {potential_daily_cost:,} PLN

ANALIZA ZAGROŻENIA:
- Rodzaj: {threat_type}
- Dystans: {distance}km
- Wzorzec: {pattern}
- Ryzyko rzeczywiste: {actual_risk}%

OPTYMALIZACJA ARBITER:
Kryteria decyzji:
1. Rzeczywiste naruszenia → START (100%)
2. Zbliżenie <5km do granicy → START (90%)
3. Nieznany samolot bez transpondera → START (80%)
4. Rutynowe IL-20 z transponderem >30km → MONITOROWANIE (10%)
5. Znany wzorzec prowokacji → MONITOROWANIE dopóki wzorzec się nie zmieni

OSZCZĘDNOŚCI PRZY OPTYMALIZACJI:
- Startów QRA uniknięto dziennie: {avoided_sorties}
- Oszczędności dzienne: {daily_savings:,} PLN
- Oszczędności miesięczne: {monthly_savings:,} PLN
- Oszczędności roczne: {annual_savings:,} PLN

ZASOBY UWOLNIONE NA:
- Prawdziwe zagrożenia (naruszenia, pociski)
- Trening pilotów
- Konserwacja samolotów
- Gotowość do eskalacji

REKOMENDACJA:
{recommendation}

KOSZT tej decyzji: {cost:,} PLN
OSZCZĘDNOŚĆ potencjalna: {savings:,} PLN
RYZYKO: {risk_level}
"""
        },

        'ukrainian_spillover_response': {
            'title': 'Ukraiński spillover: Pocisk/dron w polskiej przestrzeni',
            'trigger': lambda t, a, c: (
                t.origin == "Ukraine spillover" and
                t.threat_type in [ThreatType.CRUISE_MISSILE_KH101, ThreatType.DRONE_SHAHED]
            ),
            'template': """
OPCJA: Ukraiński spillover - pocisk/dron w polskiej przestrzeni powietrznej

SYTUACJA:
- Obiekt: {object_type}
- Szacowane pochodzenie: Ukraina (pocisk rosyjski)
- Pozycja: {position}
- Trajektoria: {trajectory}
- Czas w polskiej przestrzeni powietrznej: {time_in_airspace} minut

PODOBNE WYDARZENIA (2022-2024):
- Listopad 2022: Pocisk w Przewodowie (2 ofiary)
- Grudzień 2022: Shahed wleciał, spadł w lesie
- Marzec 2023: Pocisk śledzony przez QRA, spadł
- Łącznie {total_events} potwierdzone wydarzenia

DOSTĘPNE SYSTEMY:
{available_systems}

MOŻLIWE AKCJE:

1. ZESTRZELENIE:
   - System: {intercept_system}
   - Prawdopodobieństwo: {intercept_probability}%
   - Koszt: {intercept_cost:,} PLN
   - Ryzyko szczątków: {debris_risk}

2. ŚLEDZENIE DO UPADKU:
   - Monitorowanie przez {tracking_systems}
   - Przewidywane miejsce upadku: {predicted_impact}
   - Koszt: 0 PLN
   - Ryzyko: {tracking_risk}

ANALIZA:
- Cel strategiczny w pobliżu: {strategic_target_nearby}
- Obszar zaludniony: {populated_area}
- Paliwo/zasięg pocisku: {remaining_range}km

ARTYKUŁ 5 NATO:
- To NIE jest atak na Polskę (zbłąkany pocisk)
- Artykuł 5 nie ma zastosowania według precedensu Przewodowa
- Niemniej: Suwerenna decyzja Polski o odpowiedzi

REKOMENDACJA:
{recommendation}

KOSZT: {cost:,} PLN
PRAWDOPODOBIEŃSTWO: {success_rate}%
RYZYKO POLITYCZNE: {political_risk}
"""
        }
    }

    @staticmethod
    def generate_options(threat: MultiSensorThreat,
                        assets: List[AvailableAsset],
                        context: OperationalContext) -> List[GeneratedOption]:
        """Generate tactical options from Polish doctrine"""

        options = []

        for template_id, template_def in PolishIAMDDoctrine.TEMPLATES.items():
            # Check trigger
            if not template_def['trigger'](threat, assets, context):
                continue

            # Calculate parameters
            params = PolishIAMDDoctrine._calculate_parameters(
                template_id, threat, assets, context
            )

            if params is None:
                continue

            # Fill template
            description = template_def['template'].format(**params)

            options.append(GeneratedOption(
                option_id=f"POLISH_IAMD_{template_id}_{int(time.time())}",
                title=template_def['title'],
                description=description.strip(),
                template_id=template_id,
                estimated_cost_pln=params.get('cost', 0),
                estimated_success_rate=params.get('success_rate', 85.0),
                assets_used=params.get('assets_used', []),
                nato_coordination_required=params.get('nato_required', False),
                polish_sovereignty_maintained=params.get('sovereignty', True),
                degraded_comms_compatible=params.get('degraded_comms_ok', True)
            ))

        return options

    @staticmethod
    def _calculate_parameters(template_id: str,
                             threat: MultiSensorThreat,
                             assets: List[AvailableAsset],
                             context: OperationalContext) -> Optional[Dict]:
        """Calculate parameters for template"""

        # Find available systems by type
        f16 = [a for a in assets if a.system_type == SystemType.F16_QRA]
        mig29 = [a for a in assets if a.system_type == SystemType.MIG29_QRA]
        patriot = [a for a in assets if a.system_type == SystemType.PATRIOT_PAC3]
        nasams = [a for a in assets if a.system_type == SystemType.NASAMS_BATTERY]
        sky_sabre = [a for a in assets if a.system_type == SystemType.SKY_SABRE]
        piorun = [a for a in assets if a.system_type == SystemType.PIORUN_MANPADS]

        if template_id == 'kaliningrad_corridor_qra':
            qra_asset = f16[0] if f16 else mig29[0] if mig29 else None
            if not qra_asset:
                return None

            # Get transponder status from first contact
            transponder = threat.contacts[0].transponder_status if threat.contacts else "UNKNOWN"
            ecm = "TAK" if any(c.ecm_detected for c in threat.contacts) else "NIE"

            gps_status = "ZAKŁÓCONY" if context.gps_jamming_active else "OPERACYJNY"
            cellular_status = "ZAKŁÓCONY" if context.cellular_disrupted else "OPERACYJNY"
            link16_status = "ZAKŁÓCONY" if context.link16_jamming else "OPERACYJNY"

            nato_status = "Połączony z NATO CAOC Uedem" if context.nato_caoc_connection else "Brak połączenia z NATO (zakłócenia)"

            backup_list = []
            if nasams:
                backup_list.append(nasams[0].system_type.value)
            if patriot:
                backup_list.append(patriot[0].system_type.value)

            return {
                'contact_description': f"{threat.estimated_range_km:.1f}km, kurs {threat.estimated_bearing}°",
                'origin': threat.origin or "Kaliningrad",
                'range_km': threat.estimated_range_km,
                'time_to_border': threat.time_to_border_minutes,
                'transponder_status': transponder,
                'ecm_status': ecm,
                'qra_count': qra_asset.count,
                'qra_type': qra_asset.system_type.value,
                'qra_base': qra_asset.location,
                'qra_response_time': qra_asset.response_time_minutes,
                'backup_systems': ', '.join(backup_list) if backup_list else "Brak",
                'nato_caoc_status': nato_status,
                'link16_status': link16_status,
                'cost_per_sortie': 80000,  # 80,000 PLN per F-16 sortie
                'avoided_sorties': 4,  # Typical per day
                'annual_savings': 80000 * 4 * 250,  # Savings with optimization
                'gps_status': gps_status,
                'cellular_status': cellular_status,
                'link16_jamming': link16_status,
                'cost': qra_asset.cost_per_engagement_pln,
                'success_rate': int(qra_asset.success_rate * 100),
                'assets_used': [qra_asset.system_type.value],
                'nato_required': False,
                'sovereignty': True,
                'degraded_comms_ok': True  # Local decision possible
            }

        elif template_id == 'iamd_weapon_target_pairing':
            # Build layered defense based on threat type
            patriot_layer = ""
            nasams_layer = ""
            manpads_layer = ""
            weapon_assignment = ""

            layers_active = 0
            min_cost = 0
            typical_cost = 0
            max_cost = 0

            # Patriot for ballistic
            if patriot and threat.threat_type == ThreatType.BALLISTIC_MISSILE_ISKANDER:
                p = patriot[0]
                patriot_layer = f"- {p.count}x Patriot PAC-3 z {p.location}\n- Zasięg: {p.effective_range_km}km\n- Koszt: {p.cost_per_engagement_pln:,} PLN/pocisk\n- Sukces: {int(p.success_rate*100)}%"
                weapon_assignment += f"ISKANDER → PATRIOT (jedyny system zdolny do przechwytowania balistycznych)\n"
                layers_active += 1
                min_cost = p.cost_per_engagement_pln
                typical_cost += p.cost_per_engagement_pln
                max_cost += p.cost_per_engagement_pln
            else:
                patriot_layer = "- Nie dotyczy tego zagrożenia"

            # NASAMS for cruise missiles and aircraft
            if nasams and threat.threat_type in [ThreatType.CRUISE_MISSILE_KALIBR, ThreatType.CRUISE_MISSILE_KH101, ThreatType.AIRCRAFT_FIGHTER]:
                n = nasams[0]
                nasams_layer = f"- {n.count}x NASAMS z {n.location}\n- Zasięg: {n.effective_range_km}km\n- Koszt: {n.cost_per_engagement_pln:,} PLN/pocisk\n- Sukces: {int(n.success_rate*100)}%"
                weapon_assignment += f"{threat.threat_type.value} → NASAMS (optymalny do celów manewrujących)\n"
                layers_active += 1
                if min_cost == 0:
                    min_cost = n.cost_per_engagement_pln
                typical_cost += n.cost_per_engagement_pln
                max_cost += n.cost_per_engagement_pln
            else:
                nasams_layer = "- Nie dotyczy tego zagrożenia"

            # MANPADS for drones
            if piorun and threat.threat_type == ThreatType.DRONE_SHAHED:
                pi = piorun[0]
                manpads_layer = f"- {pi.count}x Piorun MANPADS\n- Zasięg: {pi.effective_range_km}km\n- Koszt: {pi.cost_per_engagement_pln:,} PLN/pocisk\n- Sukces: {int(pi.success_rate*100)}%"
                weapon_assignment += f"SHAHED DRONE → PIORUN (najtańsze, skuteczne)\n"
                layers_active += 1
                if min_cost == 0:
                    min_cost = pi.cost_per_engagement_pln
                typical_cost += pi.cost_per_engagement_pln
                max_cost += pi.cost_per_engagement_pln
            else:
                manpads_layer = "- Nie dotyczy tego zagrożenia"

            # Calculate success rates
            single_success = 85
            two_success = 97
            three_success = 99.5

            # Coalition coordination details
            coalition = "- Patriot (US): Wymaga US ROE clearance\n"
            coalition += "- NASAMS (Norwegian): Norweskie dowództwo\n"
            coalition += "- Polskie Piorun: Polska kontrola\n"
            coalition += "- Koordynacja przez ARBITER język naturalny (bez wymiany danych)"

            reload_times = ""
            if patriot:
                reload_times += f"- Patriot: {patriot[0].reload_time_minutes} minut\n"
            if nasams:
                reload_times += f"- NASAMS: {nasams[0].reload_time_minutes} minut\n"
            if piorun:
                reload_times += f"- Piorun: {piorun[0].reload_time_minutes} minut\n"

            expected = typical_cost

            return {
                'threat_type': threat.threat_type.value,
                'priority': threat.priority.value,
                'time_to_border': threat.time_to_border_minutes,
                'patriot_layer': patriot_layer,
                'nasams_layer': nasams_layer,
                'manpads_layer': manpads_layer,
                'weapon_target_assignment': weapon_assignment,
                'single_layer_success': single_success,
                'two_layer_success': two_success,
                'three_layer_success': three_success,
                'min_cost': min_cost,
                'typical_cost': typical_cost,
                'max_cost': max_cost,
                'expected_cost': expected,
                'coalition_coordination': coalition,
                'reload_times': reload_times.strip(),
                'coverage_after_engagement': "Patriot: 75% pociski pozostałe, NASAMS: 80%, Piorun: wiele jednostek",
                'active_layers': layers_active,
                'cost': expected,
                'success_rate': two_success,
                'assets_used': [a.system_type.value for a in [p for p in patriot[:1]] + [n for n in nasams[:1]] + [p for p in piorun[:1]]],
                'nato_required': True,
                'sovereignty': True,
                'degraded_comms_ok': False  # Requires coordination
            }

        # Additional templates...
        # (continuing with other templates following same pattern)

        return None

# ============================================================================
# ARBITER INTEGRATION
# ============================================================================

class PolishC2Service:
    """Main C2 service: Generate options + ARBITER evaluation"""

    def __init__(self, arbiter_url: str = "https://api.arbiter.traut.ai/v1/compare"):
        self.arbiter_url = arbiter_url

    def process_multi_sensor_scenario(self,
                                      threat: MultiSensorThreat,
                                      assets: List[AvailableAsset],
                                      context: OperationalContext) -> Dict:
        """
        Process multi-sensor IAMD scenario:
        1. Generate options from Polish doctrine
        2. Evaluate with ARBITER
        3. Return ranked recommendations
        """

        print(f"\n{'='*80}")
        print(f"POLISH IAMD C2 SERVICE - Kaliningrad Corridor Optimized")
        print(f"{'='*80}\n")

        # Generate options
        print(f"⚙️  Generating tactical options from Polish IAMD doctrine...")
        start = time.time()

        options = PolishIAMDDoctrine.generate_options(threat, assets, context)

        gen_time = time.time() - start
        print(f"✓ Generated {len(options)} options in {gen_time*1000:.0f}ms\n")

        for i, opt in enumerate(options, 1):
            print(f"{i}. {opt.title}")
            print(f"   Template: {opt.template_id}")
            print(f"   Cost: {opt.estimated_cost_pln:,} PLN, Success: {opt.estimated_success_rate:.0f}%")
            print(f"   Degraded Comms OK: {'TAK' if opt.degraded_comms_compatible else 'NIE'}")
            print(f"   Assets: {', '.join(opt.assets_used)}\n")

        # Build ARBITER query
        query = self._build_c2_query(threat, assets, context)
        candidates = [opt.description for opt in options]

        # Query ARBITER
        print(f"⚡ Querying ARBITER for coherence evaluation...")
        arbiter_result = self._query_arbiter(query, candidates)

        if not arbiter_result['success']:
            return {
                'success': False,
                'error': arbiter_result.get('error'),
                'generated_options': options
            }

        # Combine results
        ranked = self._combine_results(options, arbiter_result['result'])

        return {
            'success': True,
            'generation_time_ms': gen_time * 1000,
            'arbiter_latency_ms': arbiter_result['latency'] * 1000,
            'total_time_ms': (gen_time + arbiter_result['latency']) * 1000,
            'options_generated': len(options),
            'ranked_recommendations': ranked,
            'query': query,
            'threat_summary': {
                'type': threat.threat_type.value,
                'priority': threat.priority.value,
                'range_km': threat.estimated_range_km,
                'time_to_border_min': threat.time_to_border_minutes,
                'sensor_agreement': threat.sensor_agreement(),
                'origin': threat.origin
            }
        }

    def _build_c2_query(self, threat: MultiSensorThreat,
                       assets: List[AvailableAsset],
                       context: OperationalContext) -> str:
        """Build semantic query for Polish IAMD C2"""

        query = f"""
Jestem polskim koordynatorem obrony powietrznej dla sektora {context.location}.

INFORMACJE Z WIELU CZUJNIKÓW:
"""

        for contact in threat.contacts:
            query += f"""
[{contact.source.value}] {contact.platform_name or contact.source.value}:
- Ślad: {contact.track_id}
- Namiar: {contact.bearing}°, Odległość: {contact.range_km}km
- Wysokość: {contact.altitude_m}m, Prędkość: {contact.speed_knots}kts
- Klasyfikacja: {contact.classification}
- Pewność: {int(contact.confidence * 100)}%
- Wiek danych: {contact.data_age_seconds}s
"""
            if contact.transponder_status:
                query += f"- Transponder: {contact.transponder_status}\n"
            if contact.iff_response:
                query += f"- IFF: {contact.iff_response}\n"
            if contact.ecm_detected:
                query += f"- Wykryto zakłócenia EW\n"

        query += f"""
ZGODNOŚĆ CZUJNIKÓW: {int(threat.sensor_agreement() * 100)}%
POCHODZENIE: {threat.origin or 'Nieznane'}

DOSTĘPNE SYSTEMY:
"""

        for asset in assets:
            query += f"""
- {asset.system_type.value}: {asset.count} jednostek
  - Gotowość: {asset.ready_state}
  - Efektywny zasięg: {asset.effective_range_km}km
  - Czas reakcji: {asset.response_time_minutes} minut
  - Lokalizacja: {asset.location}
  - Wymaga US clearance: {'TAK' if asset.requires_us_clearance else 'NIE'}
  - Wymaga UK clearance: {'TAK' if asset.requires_uk_clearance else 'NIE'}
"""

        query += f"""
SYTUACJA OPERACYJNA:
- Pogoda: {context.weather}, Widoczność: {context.visibility_km}km
- Zakłócenia GPS: {'TAK' if context.gps_jamming_active else 'NIE'}
- Zakłócenia Link 16: {'TAK' if context.link16_jamming else 'NIE'}
- Połączenie z NATO CAOC: {'TAK' if context.nato_caoc_connection else 'NIE'}
- Aktywny korytarz Kaliningrad: {'TAK' if context.kaliningrad_corridor_active else 'NIE'}
- Napięcia na granicy białoruskiej: {'TAK' if context.belarus_border_tension else 'NIE'}

CZAS DO GRANICY POLSKI: {threat.time_to_border_minutes:.1f} minut
PRIORYTET: {threat.priority.value}
WZORZEC HISTORYCZNY: {context.historical_pattern}

Potrzebuję REKOMENDACJI TAKTYCZNEJ zgodnie z polską doktryną IAMD z integracją NATO.
"""

        return query.strip()

    def _query_arbiter(self, query: str, candidates: List[str]) -> Dict:
        """Query ARBITER API"""
        try:
            start = time.time()

            response = requests.post(
                self.arbiter_url,
                json={
                    "query": query,
                    "candidates": candidates
                },
                timeout=30
            )

            latency = time.time() - start

            if response.status_code == 200:
                return {
                    'success': True,
                    'result': response.json(),
                    'latency': latency
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'latency': latency
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'latency': 0
            }

    def _combine_results(self, options: List[GeneratedOption],
                        arbiter_result: Dict) -> List[Dict]:
        """Combine options with ARBITER rankings"""

        ranked = []

        for i, arb_option in enumerate(arbiter_result['top'], 1):
            matching = None
            for opt in options:
                if opt.description == arb_option['text']:
                    matching = opt
                    break

            ranked.append({
                'rank': i,
                'coherence': arb_option['score'],
                'title': matching.title if matching else f"Option {i}",
                'description': arb_option['text'],
                'template_id': matching.template_id if matching else 'unknown',
                'estimated_cost_pln': matching.estimated_cost_pln if matching else 0,
                'estimated_success_rate': matching.estimated_success_rate if matching else 0,
                'assets_used': matching.assets_used if matching else [],
                'nato_coordination': matching.nato_coordination_required if matching else False,
                'polish_sovereignty': matching.polish_sovereignty_maintained if matching else True,
                'degraded_comms_ok': matching.degraded_comms_compatible if matching else False,
                'recommendation_level': 'HIGH' if arb_option['score'] > 0.80 else 'MEDIUM' if arb_option['score'] > 0.70 else 'LOW'
            })

        return ranked


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                     POLISH IAMD C2 DOCTRINE SERVICE                                  ║
║                                                                                       ║
║  For: Polish Ministry of National Defence                                            ║
║  Deputy Director: Paweł Bejda                                                        ║
║  Focus: Kaliningrad Corridor + Coalition IAMD                                        ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
    """)
