"""All MCP tool handlers and the TOOL_REGISTRY / TOOL_LIST exports."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Optional

import schemas as S

if TYPE_CHECKING:
    from client import GameClient


# ── helpers ───────────────────────────────────────────────────────────────────

def _opt(args: dict, *keys) -> dict:
    """Return a dict containing only the keys present in args."""
    return {k: args[k] for k in keys if k in args}


# ── Auth ──────────────────────────────────────────────────────────────────────

async def signup(client: GameClient, args: dict) -> dict:
    data = await client._post("/signup", {"username": args["username"], "password": args["password"]})
    if data.get("ok") and data.get("api_key"):
        client.api_key = data["api_key"]
        client.start_sse_listener()
    return data


async def login(client: GameClient, args: dict) -> dict:
    data = await client._post("/login", {"username": args["username"], "password": args["password"]})
    if data.get("ok") and data.get("api_key"):
        client.api_key = data["api_key"]
        client.start_sse_listener()
    return data


async def get_auth_status(client: GameClient, args: dict) -> dict:
    return {"authenticated": bool(client.api_key), "api_key_set": client.api_key is not None}


# ── State ─────────────────────────────────────────────────────────────────────

async def get_state(client: GameClient, args: dict) -> dict:
    return await client._get("/state")


async def get_rules(client: GameClient, args: dict) -> dict:
    return await client._get("/rules")


async def get_public(client: GameClient, args: dict) -> dict:
    return await client._get("/public")


async def get_leaderboard(client: GameClient, args: dict) -> dict:
    return await client._get("/leaderboard")


# ── Submarine ─────────────────────────────────────────────────────────────────

async def register_sub(client: GameClient, args: dict) -> dict:
    return await client._post("/register_sub")


async def has_subs(client: GameClient, args: dict) -> dict:
    return await client._get("/has_subs")


async def control_sub(client: GameClient, args: dict) -> dict:
    sub_id = args["sub_id"]
    body = _opt(args, "throttle", "target_depth", "planes", "rudder_deg", "rudder_nudge_deg")
    return await client._post(f"/control/{sub_id}", body)


async def set_sub_heading(client: GameClient, args: dict) -> dict:
    return await client._post(f"/set_sub_heading/{args['sub_id']}", {"heading_deg": args["heading_deg"]})


async def turn_sub(client: GameClient, args: dict) -> dict:
    return await client._post(f"/turn_sub/{args['sub_id']}", {"turn_deg": args["turn_deg"]})


async def snorkel(client: GameClient, args: dict) -> dict:
    body = {}
    if "on" in args and args["on"] is not None:
        body["on"] = args["on"]
    return await client._post(f"/snorkel/{args['sub_id']}", body)


async def emergency_blow(client: GameClient, args: dict) -> dict:
    return await client._post(f"/emergency_blow/{args['sub_id']}")


async def set_passive_array(client: GameClient, args: dict) -> dict:
    return await client._post(f"/set_passive_array/{args['sub_id']}", {"dir_deg": args["dir_deg"]})


# ── Sonar ─────────────────────────────────────────────────────────────────────

async def ping_sonar(client: GameClient, args: dict) -> dict:
    body = {"max_range": args["max_range"]}
    if "center_bearing_deg" in args:
        body["center_bearing_deg"] = args["center_bearing_deg"]
    if "beamwidth_deg" in args:
        body["beamwidth_deg"] = args["beamwidth_deg"]
    return await client._post(f"/ping/{args['sub_id']}", body)


async def weather_scan(client: GameClient, args: dict) -> dict:
    return await client._post(f"/weather_scan/{args['sub_id']}")


# ── Weapons ───────────────────────────────────────────────────────────────────

async def launch_drone(client: GameClient, args: dict) -> dict:
    body: dict = {"range": args["range_m"]}
    if "payload_type" in args:
        body["payload_type"] = args["payload_type"]
    return await client._post(f"/launch_drone/{args['sub_id']}", body)


async def reload_drones(client: GameClient, args: dict) -> dict:
    body = {}
    if "count" in args and args["count"] is not None:
        body["count"] = args["count"]
    return await client._post(f"/reload_drones/{args['sub_id']}", body)


async def set_drone_speed(client: GameClient, args: dict) -> dict:
    return await client._post(f"/set_drone_speed/{args['drone_id']}", {"speed": args["speed"]})


async def set_drone_heading(client: GameClient, args: dict) -> dict:
    return await client._post(f"/set_torp_heading/{args['drone_id']}", {"heading_deg": args["heading_deg"]})


async def set_drone_target_heading(client: GameClient, args: dict) -> dict:
    return await client._post(f"/set_torp_target_heading/{args['drone_id']}", {"heading_deg": args["heading_deg"]})


async def set_drone_depth(client: GameClient, args: dict) -> dict:
    return await client._post(f"/set_torp_depth/{args['drone_id']}", {"depth": args["depth"]})


async def set_drone_homing(client: GameClient, args: dict) -> dict:
    return await client._post(f"/set_torp_homing/{args['drone_id']}", {"enabled": args["enabled"]})


async def drone_ping(client: GameClient, args: dict) -> dict:
    return await client._post(f"/torp_ping/{args['drone_id']}", {"max_range": args["max_range"]})


async def toggle_drone_ping(client: GameClient, args: dict) -> dict:
    return await client._post(f"/torp_ping_toggle/{args['drone_id']}")


async def toggle_drone_passive_sonar(client: GameClient, args: dict) -> dict:
    return await client._post(f"/torp_passive_sonar_toggle/{args['drone_id']}")


async def detonate(client: GameClient, args: dict) -> dict:
    return await client._post(f"/detonate/{args['drone_id']}")


async def toggle_emp_pulse(client: GameClient, args: dict) -> dict:
    body = {}
    if "on" in args and args["on"] is not None:
        body["on"] = args["on"]
    return await client._post(f"/emp_pulse_toggle/{args['drone_id']}", body)


async def toggle_detection(client: GameClient, args: dict) -> dict:
    body = {}
    if "on" in args and args["on"] is not None:
        body["on"] = args["on"]
    return await client._post(f"/detection_toggle/{args['drone_id']}", body)


async def toggle_decoy(client: GameClient, args: dict) -> dict:
    body = {}
    if "on" in args and args["on"] is not None:
        body["on"] = args["on"]
    return await client._post(f"/decoy_toggle/{args['drone_id']}", body)


# ── Fueling ───────────────────────────────────────────────────────────────────

async def call_fueler(client: GameClient, args: dict) -> dict:
    return await client._post(f"/call_fueler/{args['sub_id']}")


async def start_refuel(client: GameClient, args: dict) -> dict:
    return await client._post(f"/start_refuel/{args['sub_id']}")


# ── Stream ────────────────────────────────────────────────────────────────────

async def get_latest_snapshot(client: GameClient, args: dict) -> dict:
    snap = client.get_latest_snapshot()
    if snap is None:
        return {"ok": False, "error": "No snapshot received yet. Ensure you are authenticated and SSE is connected."}
    return {"ok": True, "snapshot": snap}


_SKIP_EVENTS = {"ping"}
_BEARING_EVENTS = {"contact", "echo", "detection_drone_bearing"}


def _add_compass(event: dict) -> dict:
    """Inject compass_bearing_deg into bearing events so callers don't need to convert."""
    import math, copy
    data = event.get("data", {})
    if "bearing" not in data:
        return event
    brg = data["bearing"]
    compass = (90.0 - math.degrees(brg)) % 360.0
    event = copy.deepcopy(event)
    event["data"]["compass_bearing_deg"] = round(compass, 1)
    if "bearing_relative" in data:
        rel = (90.0 - math.degrees(data["bearing_relative"])) % 360.0
        event["data"]["compass_bearing_relative_deg"] = round(rel, 1)
    return event


async def get_event_buffer(client: GameClient, args: dict) -> dict:
    import time as _time
    types: Optional[List[str]] = args.get("event_types") or None
    limit = int(args.get("limit", 50))
    since_seconds = args.get("since_seconds")

    events = client.get_event_buffer(types=types, limit=limit)
    import sys as _sys
    print(f"[DEBUG get_event_buffer] raw={len(events)} types={types} limit={limit} buffer_size={len(list(client._buffer))}", file=_sys.stderr, flush=True)
    if events:
        print(f"[DEBUG get_event_buffer] sample event_types={[e.get('event') for e in events[:5]]}", file=_sys.stderr, flush=True)
    events = [e for e in events if e.get("event") not in _SKIP_EVENTS]

    if since_seconds is not None:
        cutoff = _time.time() - float(since_seconds)
        events = [e for e in events if e.get("time", 0) >= cutoff]

    events = [_add_compass(e) if e.get("event") in _BEARING_EVENTS else e for e in events]
    return {"ok": True, "count": len(events), "events": events}


async def clear_event_buffer(client: GameClient, args: dict) -> dict:
    with client._buffer_lock:
        client._buffer.clear()
    return {"ok": True}


async def get_sse_status(client: GameClient, args: dict) -> dict:
    return {"ok": True, **client.sse_status()}


# ── Registry ──────────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict = {
    "signup": signup,
    "login": login,
    "get_auth_status": get_auth_status,
    "get_state": get_state,
    "get_rules": get_rules,
    "get_public": get_public,
    "get_leaderboard": get_leaderboard,
    "register_sub": register_sub,
    "has_subs": has_subs,
    "control_sub": control_sub,
    "set_sub_heading": set_sub_heading,
    "turn_sub": turn_sub,
    "snorkel": snorkel,
    "emergency_blow": emergency_blow,
    "set_passive_array": set_passive_array,
    "ping_sonar": ping_sonar,
    "weather_scan": weather_scan,
    "launch_drone": launch_drone,
    "reload_drones": reload_drones,
    "set_drone_speed": set_drone_speed,
    "set_drone_heading": set_drone_heading,
    "set_drone_target_heading": set_drone_target_heading,
    "set_drone_depth": set_drone_depth,
    "set_drone_homing": set_drone_homing,
    "drone_ping": drone_ping,
    "toggle_drone_ping": toggle_drone_ping,
    "toggle_drone_passive_sonar": toggle_drone_passive_sonar,
    "detonate": detonate,
    "toggle_emp_pulse": toggle_emp_pulse,
    "toggle_detection": toggle_detection,
    "toggle_decoy": toggle_decoy,
    "call_fueler": call_fueler,
    "start_refuel": start_refuel,
    "get_latest_snapshot": get_latest_snapshot,
    "get_event_buffer": get_event_buffer,
    "clear_event_buffer": clear_event_buffer,
    "get_sse_status": get_sse_status,
}

TOOL_LIST = [
    {
        "name": "signup",
        "description": "Create a new game account. Stores the returned API key automatically — subsequent tools use it without re-passing.",
        "inputSchema": S.SIGNUP,
    },
    {
        "name": "login",
        "description": "Log in with existing credentials. Refreshes the stored API key.",
        "inputSchema": S.LOGIN,
    },
    {
        "name": "get_auth_status",
        "description": "Check whether the MCP server currently holds a valid API key.",
        "inputSchema": S.GET_AUTH_STATUS,
    },
    {
        "name": "get_state",
        "description": "Get your submarines, active drones/torpedoes, and fuelers. Returns positions, headings, battery, health, depth, speed. Auth required.",
        "inputSchema": S.GET_STATE,
    },
    {
        "name": "get_rules",
        "description": "Retrieve the full game configuration: tick_hz, world bounds, sub physics limits, torpedo/drone specs, sonar params. Call once at session start to understand game constants.",
        "inputSchema": S.GET_RULES,
    },
    {
        "name": "get_public",
        "description": "Get the game ring boundary (safe zone) and objective locations. Returns {ring: {x,y,r}, objectives: [...]}.",
        "inputSchema": S.GET_PUBLIC,
    },
    {
        "name": "get_leaderboard",
        "description": "Get current scores, kills, and sub counts for all players.",
        "inputSchema": S.GET_LEADERBOARD,
    },
    {
        "name": "register_sub",
        "description": "Spawn a new submarine. Returns sub_id and spawn coordinates [x,y,depth]. Call this after login/signup to enter the game.",
        "inputSchema": S.REGISTER_SUB,
    },
    {
        "name": "has_subs",
        "description": "Check whether you have active submarines. Returns {has_subs, count}. Use to detect death or confirm spawn.",
        "inputSchema": S.HAS_SUBS,
    },
    {
        "name": "control_sub",
        "description": "Set submarine propulsion and depth. throttle: 0.0–1.0 (speed). target_depth: meters (autopilot, null to clear). planes: -1.0=dive, +1.0=climb. rudder_deg: absolute rudder angle. rudder_nudge_deg: relative rudder adjustment. All fields optional.",
        "inputSchema": S.CONTROL_SUB,
    },
    {
        "name": "set_sub_heading",
        "description": "Set target compass heading (0=North, 90=East, 180=South, 270=West). Sub steers automatically toward this heading.",
        "inputSchema": S.SET_SUB_HEADING,
    },
    {
        "name": "turn_sub",
        "description": "Apply a relative turn from current heading. Positive=right (starboard), negative=left (port).",
        "inputSchema": S.TURN_SUB,
    },
    {
        "name": "snorkel",
        "description": "Toggle or set snorkel mode. Snorkeling recharges battery but increases acoustic signature. Must be at or above snorkel_depth. on=null toggles.",
        "inputSchema": S.SNORKEL,
    },
    {
        "name": "emergency_blow",
        "description": "Rapidly surface using blow charge. Use when critically deep or heavily damaged. Consumes one-time blow charge.",
        "inputSchema": S.EMERGENCY_BLOW,
    },
    {
        "name": "set_passive_array",
        "description": "Electronically steer the passive sonar array toward dir_deg degrees to improve detection sensitivity in that direction.",
        "inputSchema": S.SET_PASSIVE_ARRAY,
    },
    {
        "name": "ping_sonar",
        "description": "Fire an active sonar ping. Returns battery cost. Echo contacts arrive asynchronously via SSE stream (use get_event_buffer with type 'echo'). WARNING: active pings reveal your position to nearby enemies. Narrower beamwidth = lower battery cost but requires aiming.",
        "inputSchema": S.PING_SONAR,
    },
    {
        "name": "weather_scan",
        "description": "Scan for sonar-cloud hazards. Returns cloud bearings, ranges, radii, and depth bands. Makes sub acoustically noisy briefly.",
        "inputSchema": S.WEATHER_SCAN,
    },
    {
        "name": "launch_drone",
        "description": "Launch a drone. payload_type: 'explosive' (torpedo, damages subs), 'detection' (triangulates targets), 'decoy' (fake sub contact on enemy sonar), 'emp' (disables homing/controls in radius). range_m = max wire length before cut. Max 4 active drones per sub. Returns drone_id.",
        "inputSchema": S.LAUNCH_DRONE,
    },
    {
        "name": "reload_drones",
        "description": "Reload drone magazine. Costs battery. Cannot reload if 4 drones are active. count=null fills all available slots.",
        "inputSchema": S.RELOAD_DRONES,
    },
    {
        "name": "set_drone_speed",
        "description": "Set drone target speed in m/s. Explosive/EMP: 8–18 m/s. Detection drones have enforced slower speed. Slower = longer battery life.",
        "inputSchema": S.SET_DRONE_SPEED,
    },
    {
        "name": "set_drone_heading",
        "description": "Immediate absolute heading command for drone in wire mode (compass degrees). Returns error 'wire lost' if drone exceeded its range.",
        "inputSchema": S.SET_DRONE_HEADING,
    },
    {
        "name": "set_drone_target_heading",
        "description": "Set auto-steering target heading for drone (compass degrees). Drone smoothly steers toward this heading.",
        "inputSchema": S.SET_DRONE_TARGET_HEADING,
    },
    {
        "name": "set_drone_depth",
        "description": "Set drone target depth in meters. Drone autopilots to this depth.",
        "inputSchema": S.SET_DRONE_DEPTH,
    },
    {
        "name": "set_drone_homing",
        "description": "Enable/disable autonomous homing. When enabled, drone uses its own sonar to hunt enemy subs (fire-and-forget). Automatically enables auto-ping.",
        "inputSchema": S.SET_DRONE_HOMING,
    },
    {
        "name": "drone_ping",
        "description": "Manual active sonar ping from a drone. Returns immediate contacts {bearing, range, depth}. Use to aim before detonation.",
        "inputSchema": S.DRONE_PING,
    },
    {
        "name": "toggle_drone_ping",
        "description": "Toggle drone auto-ping mode. When active, drone periodically pings and torpedo_ping events arrive on your SSE stream.",
        "inputSchema": S.TOGGLE_DRONE_PING,
    },
    {
        "name": "toggle_drone_passive_sonar",
        "description": "Toggle drone passive sonar. Passive contacts arrive as torpedo_contact events on your SSE stream.",
        "inputSchema": S.TOGGLE_DRONE_PASSIVE_SONAR,
    },
    {
        "name": "detonate",
        "description": "Command-detonate drone at current position. Only explosive drones damage subs. Returns number of entities affected.",
        "inputSchema": S.DETONATE,
    },
    {
        "name": "toggle_emp_pulse",
        "description": "Toggle EMP pulse mode on EMP drones. Pulses every ~3s in 300m radius, disabling homing/controls/active sonar on targets. EMP drones only. on=null toggles.",
        "inputSchema": S.TOGGLE_EMP_PULSE,
    },
    {
        "name": "toggle_detection",
        "description": "Toggle detection mode on detection drones. When enabled, actively triangulates targets and sends bearing reports via SSE. Detection drones only. on=null toggles.",
        "inputSchema": S.TOGGLE_DETECTION,
    },
    {
        "name": "toggle_decoy",
        "description": "Toggle decoy mode on decoy drones. When active, drone appears as a submarine contact on enemy passive sonar for tactical deception. Decoy drones only. on=null toggles.",
        "inputSchema": S.TOGGLE_DECOY,
    },
    {
        "name": "call_fueler",
        "description": "Summon a fueler NPC. Spawns 1000–3000m away on the surface. Visible to all players — reveals your approximate position. One active fueler per account.",
        "inputSchema": S.CALL_FUELER,
    },
    {
        "name": "start_refuel",
        "description": "Begin server-controlled refueling. Must be within 50m of your fueler. Server enables snorkel, drives sub to surface, and freezes propulsion during refuel.",
        "inputSchema": S.START_REFUEL,
    },
    {
        "name": "get_latest_snapshot",
        "description": "Return the most recent game state snapshot from the SSE stream. Fastest way to check current positions/status without a REST call. Returns null if no snapshot received yet.",
        "inputSchema": S.GET_LATEST_SNAPSHOT,
    },
    {
        "name": "get_event_buffer",
        "description": "Return recent SSE events from the in-memory buffer. event_types filter options: contact, echo, explosion, torpedo_contact, torpedo_ping, emp_pulse, drone_expired. Use this to read sonar returns after a ping or detect nearby explosions.",
        "inputSchema": S.GET_EVENT_BUFFER,
    },
    {
        "name": "clear_event_buffer",
        "description": "Clear the event buffer. Use after processing a batch of events to avoid re-processing stale contacts.",
        "inputSchema": S.CLEAR_EVENT_BUFFER,
    },
    {
        "name": "get_sse_status",
        "description": "Check SSE connection health. Returns connected status, total events received, last event time, and buffer size.",
        "inputSchema": S.GET_SSE_STATUS,
    },
]
