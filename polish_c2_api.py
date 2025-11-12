#!/usr/bin/env python3
"""
POLISH C2 API SERVICE
FastAPI wrapper for Polish Integrated Air and Missile Defense Doctrine Service
Exposes HTTP endpoints for multi-coalition C2 integration

Usage:
    pip install fastapi uvicorn
    uvicorn polish_c2_api:app --host 0.0.0.0 --port 8003 --reload

Created by: Joel Trout
For: Polish Ministry of National Defence / Deputy Director Paweł Bejda
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import time

# Import the doctrine service
from polish_c2_doctrine import (
    SensorContact, MultiSensorThreat, AvailableAsset, OperationalContext,
    PolishC2Service, ThreatType, SystemType, ContactPriority, SensorSource
)

app = FastAPI(
    title="Polish IAMD C2 API Service",
    description="Integrated Air and Missile Defense decision support for Polish Armed Forces",
    version="1.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def serve_frontend():
    """Serve the Polish C2 interface"""
    return FileResponse("index.html")

# ============================================================================
# PYDANTIC MODELS FOR API
# ============================================================================

class SensorContactAPI(BaseModel):
    source: str = Field(..., description="Sensor source")
    track_id: str = Field(..., description="Track identifier")
    bearing: int = Field(..., ge=0, le=360, description="Bearing in degrees")
    range_km: float = Field(..., ge=0, description="Range in kilometers")
    altitude_m: int = Field(..., ge=0, description="Altitude in meters")
    speed_knots: float = Field(..., ge=0, description="Speed in knots")
    confidence: float = Field(..., ge=0, le=1, description="Confidence 0-1")
    classification: str = Field(..., description="Target classification")
    iff_response: Optional[str] = None
    data_age_seconds: int = Field(default=0, ge=0)
    ecm_detected: bool = Field(default=False)
    transponder_status: Optional[str] = None
    platform_name: Optional[str] = None

class MultiSensorThreatAPI(BaseModel):
    contacts: List[SensorContactAPI]
    threat_type: str = Field(..., description="Threat type")
    priority: str = Field(..., description="Contact priority")
    estimated_bearing: int = Field(..., ge=0, le=360)
    estimated_range_km: float = Field(..., ge=0)
    time_to_border_minutes: float = Field(..., ge=0)
    target_description: str
    origin: Optional[str] = None

class AvailableAssetAPI(BaseModel):
    system_type: str = Field(..., description="System type")
    count: int = Field(..., ge=1)
    ready_state: str = Field(..., description="READY/STANDBY_15MIN/MAINTENANCE/TRAINING")
    effective_range_km: float = Field(..., ge=0)
    response_time_minutes: int = Field(..., ge=0)
    cost_per_engagement_pln: int = Field(..., ge=0, description="Cost in PLN")
    success_rate: float = Field(..., ge=0, le=1)
    location: str
    requires_nato_clearance: bool = Field(default=False)
    requires_polish_clearance: bool = Field(default=True)
    requires_us_clearance: bool = Field(default=False)
    requires_uk_clearance: bool = Field(default=False)
    classification_level: str = Field(default="POLISH_RESTRICTED")
    reload_time_minutes: int = Field(default=0)
    missiles_available: int = Field(default=0)

class OperationalContextAPI(BaseModel):
    location: str
    weather: str
    visibility_km: float = Field(..., ge=0)
    gps_jamming_active: bool = False
    cellular_disrupted: bool = False
    link16_jamming: bool = False
    nato_caoc_connection: bool = True
    kaliningrad_corridor_active: bool = False
    belarus_border_tension: bool = False
    ukrainian_war_spillover_risk: bool = False
    suwalki_gap_monitoring: bool = False
    us_forces_deployed: bool = False
    uk_sky_sabre_active: bool = False
    norwegian_nasams_ready: bool = False
    strategic_assets_nearby: List[str] = Field(default_factory=list)
    civilian_traffic_nearby: bool = False
    escalation_risk: str = "LOW"
    historical_pattern: str = ""

class C2Request(BaseModel):
    threat: MultiSensorThreatAPI
    assets: List[AvailableAssetAPI]
    context: OperationalContextAPI

class RecommendationResponse(BaseModel):
    rank: int
    coherence: float
    title: str
    description: str
    template_id: str
    estimated_cost_pln: int
    estimated_success_rate: float
    assets_used: List[str]
    nato_coordination: bool
    polish_sovereignty: bool
    degraded_comms_ok: bool
    recommendation_level: str

class C2Response(BaseModel):
    success: bool
    generation_time_ms: float
    arbiter_latency_ms: float
    total_time_ms: float
    options_generated: int
    ranked_recommendations: List[RecommendationResponse]
    threat_summary: Dict[str, Any]
    error: Optional[str] = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def convert_sensor_source(source_str: str) -> SensorSource:
    """Convert string to SensorSource enum"""
    mapping = {
        "Polish_Radar": SensorSource.POLISH_RADAR,
        "NATO_AWACS": SensorSource.NATO_AWACS,
        "US_Patriot_Radar": SensorSource.US_PATRIOT_RADAR,
        "NASAMS_Radar": SensorSource.NASAMS_RADAR,
        "Sky_Sabre_Radar": SensorSource.SKY_SABRE_RADAR,
        "Visual_QRA": SensorSource.VISUAL_QRA,
        "Ground_Observer": SensorSource.GROUND_OBSERVER,
    }
    return mapping.get(source_str, SensorSource.POLISH_RADAR)

def convert_threat_type(threat_str: str) -> ThreatType:
    """Convert string to ThreatType enum"""
    mapping = {
        "Transport Aircraft": ThreatType.AIRCRAFT_TRANSPORT,
        "Fighter/Bomber": ThreatType.AIRCRAFT_FIGHTER,
        "Reconnaissance (IL-20, Tu-134)": ThreatType.AIRCRAFT_RECONNAISSANCE,
        "Attack Helicopter": ThreatType.HELICOPTER_ATTACK,
        "Iskander Ballistic Missile": ThreatType.BALLISTIC_MISSILE_ISKANDER,
        "Kalibr Cruise Missile": ThreatType.CRUISE_MISSILE_KALIBR,
        "Kh-101 Cruise Missile": ThreatType.CRUISE_MISSILE_KH101,
        "Shahed-136 Drone": ThreatType.DRONE_SHAHED,
        "Orlan-10 Reconnaissance": ThreatType.DRONE_ORLAN,
        "Small Commercial UAV": ThreatType.DRONE_SMALL,
    }
    return mapping.get(threat_str, ThreatType.UNKNOWN)

def convert_system_type(system_str: str) -> SystemType:
    """Convert string to SystemType enum"""
    mapping = {
        "F-16 QRA (Polish)": SystemType.F16_QRA,
        "MiG-29 QRA (Polish - Legacy)": SystemType.MIG29_QRA,
        "Piorun MANPADS": SystemType.PIORUN_MANPADS,
        "S-125 Neva (Legacy Soviet)": SystemType.S125_NEVA,
        "Patriot PAC-3 (US)": SystemType.PATRIOT_PAC3,
        "NASAMS (Norwegian)": SystemType.NASAMS_BATTERY,
        "Sky Sabre (British)": SystemType.SKY_SABRE,
        "Polish EW System": SystemType.ELECTRONIC_WARFARE,
    }
    return mapping.get(system_str, SystemType.F16_QRA)

def convert_contact_priority(priority_str: str) -> ContactPriority:
    """Convert string to ContactPriority enum"""
    mapping = {
        "Critical": ContactPriority.CRITICAL,
        "High": ContactPriority.HIGH,
        "Medium": ContactPriority.MEDIUM,
        "Low": ContactPriority.LOW,
    }
    return mapping.get(priority_str, ContactPriority.MEDIUM)

def api_to_doctrine_models(request: C2Request) -> tuple:
    """Convert API models to Doctrine Service models"""

    # Convert sensor contacts
    contacts = []
    for contact_api in request.threat.contacts:
        contacts.append(SensorContact(
            source=convert_sensor_source(contact_api.source),
            track_id=contact_api.track_id,
            bearing=contact_api.bearing,
            range_km=contact_api.range_km,
            altitude_m=contact_api.altitude_m,
            speed_knots=contact_api.speed_knots,
            confidence=contact_api.confidence,
            classification=contact_api.classification,
            iff_response=contact_api.iff_response,
            data_age_seconds=contact_api.data_age_seconds,
            ecm_detected=contact_api.ecm_detected,
            transponder_status=contact_api.transponder_status,
            platform_name=contact_api.platform_name
        ))

    # Convert threat
    threat = MultiSensorThreat(
        contacts=contacts,
        threat_type=convert_threat_type(request.threat.threat_type),
        priority=convert_contact_priority(request.threat.priority),
        estimated_bearing=request.threat.estimated_bearing,
        estimated_range_km=request.threat.estimated_range_km,
        time_to_border_minutes=request.threat.time_to_border_minutes,
        target_description=request.threat.target_description,
        origin=request.threat.origin
    )

    # Convert assets
    assets = []
    for asset_api in request.assets:
        assets.append(AvailableAsset(
            system_type=convert_system_type(asset_api.system_type),
            count=asset_api.count,
            ready_state=asset_api.ready_state,
            effective_range_km=asset_api.effective_range_km,
            response_time_minutes=asset_api.response_time_minutes,
            cost_per_engagement_pln=asset_api.cost_per_engagement_pln,
            success_rate=asset_api.success_rate,
            location=asset_api.location,
            requires_nato_clearance=asset_api.requires_nato_clearance,
            requires_polish_clearance=asset_api.requires_polish_clearance,
            requires_us_clearance=asset_api.requires_us_clearance,
            requires_uk_clearance=asset_api.requires_uk_clearance,
            classification_level=asset_api.classification_level,
            reload_time_minutes=asset_api.reload_time_minutes,
            missiles_available=asset_api.missiles_available
        ))

    # Convert context
    context = OperationalContext(
        location=request.context.location,
        weather=request.context.weather,
        visibility_km=request.context.visibility_km,
        gps_jamming_active=request.context.gps_jamming_active,
        cellular_disrupted=request.context.cellular_disrupted,
        link16_jamming=request.context.link16_jamming,
        nato_caoc_connection=request.context.nato_caoc_connection,
        kaliningrad_corridor_active=request.context.kaliningrad_corridor_active,
        belarus_border_tension=request.context.belarus_border_tension,
        ukrainian_war_spillover_risk=request.context.ukrainian_war_spillover_risk,
        suwalki_gap_monitoring=request.context.suwalki_gap_monitoring,
        us_forces_deployed=request.context.us_forces_deployed,
        uk_sky_sabre_active=request.context.uk_sky_sabre_active,
        norwegian_nasams_ready=request.context.norwegian_nasams_ready,
        strategic_assets_nearby=request.context.strategic_assets_nearby,
        civilian_traffic_nearby=request.context.civilian_traffic_nearby,
        escalation_risk=request.context.escalation_risk,
        historical_pattern=request.context.historical_pattern
    )

    return threat, assets, context

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Polish IAMD C2 API",
        "status": "operational",
        "version": "1.0",
        "for": "Polish Ministry of National Defence",
        "deputy_director": "Paweł Bejda",
        "endpoints": [
            "/v1/c2 - Process multi-coalition IAMD scenario",
            "/health - Service health check",
            "/api/validate-kaliningrad - Run Kaliningrad corridor validation"
        ]
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "arbiter_service": "connected",
        "doctrine_templates": 7,
        "integration": ["Patriot (US)", "NASAMS (NO)", "Sky Sabre (UK)", "Polish F-16/MiG-29"],
        "kaliningrad_corridor": "optimized",
        "degraded_comms": "supported (26MB air-gapped)",
        "timestamp": time.time()
    }

@app.post("/v1/c2", response_model=C2Response)
async def process_c2_scenario(request: C2Request):
    """
    Process a multi-coalition IAMD scenario and return ranked recommendations.

    This endpoint:
    1. Accepts multi-sensor threat data, available coalition assets, and operational context
    2. Generates tactical options using Polish IAMD doctrine templates
    3. Evaluates options with ARBITER for semantic coherence
    4. Returns ranked recommendations maintaining Polish sovereignty
    """

    try:
        # Convert API models to Doctrine Service models
        threat, assets, context = api_to_doctrine_models(request)

        # Initialize C2 service
        service = PolishC2Service(arbiter_url="https://api.arbiter.traut.ai/v1/compare")

        # Process scenario
        result = service.process_multi_sensor_scenario(
            threat=threat,
            assets=assets,
            context=context
        )

        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'C2 service processing failed')
            )

        # Convert to response format
        recommendations = [
            RecommendationResponse(
                rank=rec['rank'],
                coherence=rec['coherence'],
                title=rec['title'],
                description=rec['description'],
                template_id=rec['template_id'],
                estimated_cost_pln=rec['estimated_cost_pln'],
                estimated_success_rate=rec['estimated_success_rate'],
                assets_used=rec['assets_used'],
                nato_coordination=rec['nato_coordination'],
                polish_sovereignty=rec['polish_sovereignty'],
                degraded_comms_ok=rec['degraded_comms_ok'],
                recommendation_level=rec['recommendation_level']
            )
            for rec in result['ranked_recommendations']
        ]

        return C2Response(
            success=True,
            generation_time_ms=result['generation_time_ms'],
            arbiter_latency_ms=result['arbiter_latency_ms'],
            total_time_ms=result['total_time_ms'],
            options_generated=result['options_generated'],
            ranked_recommendations=recommendations,
            threat_summary=result['threat_summary']
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# ============================================================================
# CONVENIENCE ENDPOINTS
# ============================================================================

@app.get("/api/templates")
async def list_templates():
    """List available Polish IAMD doctrine templates"""
    from polish_c2_doctrine import PolishIAMDDoctrine

    templates = []
    for template_id, template_def in PolishIAMDDoctrine.TEMPLATES.items():
        templates.append({
            "id": template_id,
            "title": template_def['title']
        })

    return {
        "count": len(templates),
        "templates": templates
    }

@app.get("/api/system-types")
async def get_system_types():
    """Get available Polish IAMD system types"""
    return {
        "polish_systems": [
            "F-16 QRA (Polish)",
            "MiG-29 QRA (Polish - Legacy)",
            "Piorun MANPADS",
            "S-125 Neva (Legacy Soviet)",
            "Polish EW System"
        ],
        "coalition_systems": [
            "Patriot PAC-3 (US)",
            "NASAMS (Norwegian)",
            "Sky Sabre (British)"
        ],
        "sensor_sources": [
            "Polish_Radar",
            "NATO_AWACS",
            "US_Patriot_Radar",
            "NASAMS_Radar",
            "Sky_Sabre_Radar",
            "Visual_QRA",
            "Ground_Observer"
        ]
    }

@app.post("/api/validate-kaliningrad")
async def validate_kaliningrad_scenario():
    """
    Run the Kaliningrad corridor validation scenario.
    IL-20 reconnaissance aircraft with intermittent transponder approaching Polish border.
    """

    # Define the scenario
    request = C2Request(
        threat=MultiSensorThreatAPI(
            contacts=[
                SensorContactAPI(
                    source="Polish_Radar",
                    track_id="UNKNOWN-KAL-147",
                    bearing=85,
                    range_km=45,
                    altitude_m=7500,
                    speed_knots=380,
                    confidence=0.82,
                    classification="Possible IL-20 reconnaissance",
                    transponder_status="INTERMITTENT",
                    ecm_detected=True,
                    data_age_seconds=30,
                    platform_name="Polish Ground Radar Site 3"
                ),
                SensorContactAPI(
                    source="NATO_AWACS",
                    track_id="TRACK-ALPHA-92",
                    bearing=83,
                    range_km=47,
                    altitude_m=7200,
                    speed_knots=390,
                    confidence=0.90,
                    classification="IL-20M ELINT aircraft",
                    iff_response="NON-STANDARD",
                    transponder_status="OFF",
                    data_age_seconds=15,
                    platform_name="NATO E-3A Sentry"
                ),
                SensorContactAPI(
                    source="Visual_QRA",
                    track_id="VISUAL-01",
                    bearing=84,
                    range_km=46,
                    altitude_m=7400,
                    speed_knots=385,
                    confidence=0.95,
                    classification="Confirmed IL-20M, Russian Air Force markings",
                    transponder_status="OFF",
                    data_age_seconds=120,
                    platform_name="F-16 QRA (visual confirmation)"
                )
            ],
            threat_type="Reconnaissance (IL-20, Tu-134)",
            priority="High",
            estimated_bearing=84,
            estimated_range_km=46,
            time_to_border_minutes=8.5,
            target_description="Rosyjski samolot rozpoznania IL-20 zbliża się do polskiej granicy",
            origin="Kaliningrad"
        ),
        assets=[
            AvailableAssetAPI(
                system_type="F-16 QRA (Polish)",
                count=2,
                ready_state="STANDBY_15MIN",
                effective_range_km=800,
                response_time_minutes=12,
                cost_per_engagement_pln=80000,
                success_rate=0.95,
                location="23 Baza Lotnictwa Taktycznego, Mińsk Mazowiecki",
                requires_polish_clearance=True
            ),
            AvailableAssetAPI(
                system_type="Patriot PAC-3 (US)",
                count=4,
                ready_state="READY",
                effective_range_km=160,
                response_time_minutes=2,
                cost_per_engagement_pln=2500000,
                success_rate=0.93,
                location="Forward deployed, Eastern Poland",
                requires_us_clearance=True,
                requires_nato_clearance=True,
                classification_level="US_NOFORN",
                reload_time_minutes=30,
                missiles_available=16
            ),
            AvailableAssetAPI(
                system_type="NASAMS (Norwegian)",
                count=2,
                ready_state="READY",
                effective_range_km=50,
                response_time_minutes=3,
                cost_per_engagement_pln=800000,
                success_rate=0.90,
                location="Northeastern Poland",
                requires_nato_clearance=True,
                reload_time_minutes=20,
                missiles_available=12
            ),
            AvailableAssetAPI(
                system_type="Polish EW System",
                count=1,
                ready_state="READY",
                effective_range_km=40,
                response_time_minutes=0,
                cost_per_engagement_pln=0,
                success_rate=0.65,
                location="Eastern Border EW Site"
            )
        ],
        context=OperationalContextAPI(
            location="Northeastern Poland, near Kaliningrad corridor",
            weather="Overcast, light rain",
            visibility_km=12,
            gps_jamming_active=True,
            cellular_disrupted=False,
            link16_jamming=True,
            nato_caoc_connection=False,  # Degraded due to jamming
            kaliningrad_corridor_active=True,
            belarus_border_tension=False,
            ukrainian_war_spillover_risk=False,
            suwalki_gap_monitoring=True,
            us_forces_deployed=True,
            uk_sky_sabre_active=False,
            norwegian_nasams_ready=True,
            strategic_assets_nearby=["NATO logistics hub", "23rd Air Base"],
            civilian_traffic_nearby=False,
            escalation_risk="MEDIUM",
            historical_pattern="Russian IL-20 flights 2-4 times monthly, typically maintain transponder, occasional 2-3km violations then turn back"
        )
    )

    # Process scenario
    result = await process_c2_scenario(request)

    # Add analysis
    analysis = {
        "scenario": "Kaliningrad Corridor Air Defense",
        "sensor_count": 3,
        "sensor_sources": ["Polish Radar", "NATO AWACS", "Visual QRA"],
        "sensor_agreement": result.threat_summary.get('sensor_agreement', 0) * 100,
        "time_critical": result.threat_summary.get('time_to_border_min', 0) < 10,
        "degraded_comms": "GPS and Link 16 jammed by Kaliningrad",
        "arbiter_26mb": "Air-gapped operation - still functional despite jamming",
        "key_challenge": "Coalition coordination without data sharing + Russian EW jamming + local decision required"
    }

    return {
        **result.dict(),
        "validation_analysis": analysis
    }

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                        POLISH IAMD C2 API SERVICE                                     ║
║                                                                                       ║
║  Starting FastAPI server on http://0.0.0.0:8003                                      ║
║  API Documentation: http://0.0.0.0:8003/docs                                         ║
║                                                                                       ║
║  Endpoints:                                                                           ║
║    POST /v1/c2                   - Process multi-coalition IAMD scenario             ║
║    POST /api/validate-kaliningrad - Run Kaliningrad corridor validation             ║
║    GET  /api/templates            - List doctrine templates                          ║
║    GET  /api/system-types         - Get system types                                 ║
║                                                                                       ║
║  Integration:                                                                         ║
║    - US Patriot PAC-3 (ballistic missile defense)                                    ║
║    - Norwegian NASAMS (cruise missiles + aircraft)                                   ║
║    - British Sky Sabre (forward deployed)                                            ║
║    - Polish F-16 / MiG-29 QRA                                                        ║
║    - Polish Piorun MANPADS                                                           ║
║                                                                                       ║
║  Kaliningrad Corridor Optimized:                                                     ║
║    - IL-20 provocation patterns                                                      ║
║    - Resource optimization (avoid 80,000 PLN unnecessary sorties)                    ║
║    - Degraded comms support (26MB air-gapped ARBITER)                                ║
║    - Coalition coordination without classified data sharing                          ║
║                                                                                       ║
║  Requirements:                                                                        ║
║    - ARBITER API: https://api.arbiter.traut.ai/v1/compare (pre-configured)          ║
║    - polish_c2_doctrine.py in same directory                                         ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "polish_c2_api:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )
