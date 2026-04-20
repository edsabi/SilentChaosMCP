"""JSON Schema definitions for every MCP tool input."""

# ── Auth ──────────────────────────────────────────────────────────────────────

SIGNUP = {
    "type": "object",
    "required": ["username", "password"],
    "properties": {
        "username": {"type": "string", "description": "Account username"},
        "password": {"type": "string", "description": "Account password"},
    },
}

LOGIN = {
    "type": "object",
    "required": ["username", "password"],
    "properties": {
        "username": {"type": "string"},
        "password": {"type": "string"},
    },
}

GET_AUTH_STATUS = {"type": "object", "properties": {}}

# ── State ─────────────────────────────────────────────────────────────────────

GET_STATE = {"type": "object", "properties": {}}
GET_RULES = {"type": "object", "properties": {}}
GET_PUBLIC = {"type": "object", "properties": {}}
GET_LEADERBOARD = {"type": "object", "properties": {}}

# ── Submarine ─────────────────────────────────────────────────────────────────

REGISTER_SUB = {"type": "object", "properties": {}}

HAS_SUBS = {"type": "object", "properties": {}}

CONTROL_SUB = {
    "type": "object",
    "required": ["sub_id"],
    "properties": {
        "sub_id": {"type": "string", "description": "Submarine ID"},
        "throttle": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Propulsion power 0.0–1.0",
        },
        "target_depth": {
            "type": ["number", "null"],
            "description": "Depth autopilot target in meters (null to clear)",
        },
        "planes": {
            "type": "number",
            "minimum": -1.0,
            "maximum": 1.0,
            "description": "Diving planes: -1.0=full dive, +1.0=full climb",
        },
        "rudder_deg": {
            "type": "number",
            "description": "Absolute rudder angle in degrees (±max_rudder_deg)",
        },
        "rudder_nudge_deg": {
            "type": "number",
            "description": "Relative rudder adjustment in degrees",
        },
    },
}

SET_SUB_HEADING = {
    "type": "object",
    "required": ["sub_id", "heading_deg"],
    "properties": {
        "sub_id": {"type": "string"},
        "heading_deg": {
            "type": "number",
            "description": "Target compass heading: 0=North, 90=East, 180=South, 270=West",
        },
    },
}

TURN_SUB = {
    "type": "object",
    "required": ["sub_id", "turn_deg"],
    "properties": {
        "sub_id": {"type": "string"},
        "turn_deg": {
            "type": "number",
            "description": "Relative turn: positive=right (starboard), negative=left (port)",
        },
    },
}

SNORKEL = {
    "type": "object",
    "required": ["sub_id"],
    "properties": {
        "sub_id": {"type": "string"},
        "on": {
            "type": ["boolean", "null"],
            "description": "true=enable, false=disable, null=toggle",
        },
    },
}

EMERGENCY_BLOW = {
    "type": "object",
    "required": ["sub_id"],
    "properties": {"sub_id": {"type": "string"}},
}

SET_PASSIVE_ARRAY = {
    "type": "object",
    "required": ["sub_id", "dir_deg"],
    "properties": {
        "sub_id": {"type": "string"},
        "dir_deg": {
            "type": "number",
            "description": "Direction to steer passive sonar array (compass degrees)",
        },
    },
}

# ── Sonar ─────────────────────────────────────────────────────────────────────

PING_SONAR = {
    "type": "object",
    "required": ["sub_id", "max_range"],
    "properties": {
        "sub_id": {"type": "string"},
        "max_range": {"type": "number", "description": "Maximum ping range in meters"},
        "center_bearing_deg": {
            "type": "number",
            "default": 0.0,
            "description": "Center bearing of the beam (compass degrees)",
        },
        "beamwidth_deg": {
            "type": "number",
            "default": 360.0,
            "description": "Beam width in degrees; 360=omnidirectional, narrower=cheaper",
        },
    },
}

WEATHER_SCAN = {
    "type": "object",
    "required": ["sub_id"],
    "properties": {"sub_id": {"type": "string"}},
}

# ── Weapons ───────────────────────────────────────────────────────────────────

LAUNCH_DRONE = {
    "type": "object",
    "required": ["sub_id", "range_m"],
    "properties": {
        "sub_id": {"type": "string"},
        "range_m": {
            "type": "number",
            "description": "Maximum wire length / range before wire is cut (meters)",
        },
        "payload_type": {
            "type": "string",
            "enum": ["explosive", "detection", "decoy", "emp"],
            "default": "explosive",
            "description": "explosive=torpedo, detection=triangulates targets, decoy=false contact, emp=disables systems",
        },
    },
}

RELOAD_DRONES = {
    "type": "object",
    "required": ["sub_id"],
    "properties": {
        "sub_id": {"type": "string"},
        "count": {
            "type": ["integer", "null"],
            "description": "Number of slots to reload; null=fill all available",
        },
    },
}

SET_DRONE_SPEED = {
    "type": "object",
    "required": ["drone_id", "speed"],
    "properties": {
        "drone_id": {"type": "string"},
        "speed": {"type": "number", "description": "Target speed in m/s"},
    },
}

SET_DRONE_HEADING = {
    "type": "object",
    "required": ["drone_id", "heading_deg"],
    "properties": {
        "drone_id": {"type": "string"},
        "heading_deg": {
            "type": "number",
            "description": "Immediate absolute heading command (compass degrees)",
        },
    },
}

SET_DRONE_TARGET_HEADING = {
    "type": "object",
    "required": ["drone_id", "heading_deg"],
    "properties": {
        "drone_id": {"type": "string"},
        "heading_deg": {
            "type": "number",
            "description": "Autopilot target heading (compass degrees)",
        },
    },
}

SET_DRONE_DEPTH = {
    "type": "object",
    "required": ["drone_id", "depth"],
    "properties": {
        "drone_id": {"type": "string"},
        "depth": {"type": "number", "description": "Target depth in meters"},
    },
}

SET_DRONE_HOMING = {
    "type": "object",
    "required": ["drone_id", "enabled"],
    "properties": {
        "drone_id": {"type": "string"},
        "enabled": {
            "type": "boolean",
            "description": "true=autonomous homing hunt mode, false=wire control",
        },
    },
}

DRONE_PING = {
    "type": "object",
    "required": ["drone_id", "max_range"],
    "properties": {
        "drone_id": {"type": "string"},
        "max_range": {"type": "number", "description": "Ping range in meters"},
    },
}

TOGGLE_DRONE_PING = {
    "type": "object",
    "required": ["drone_id"],
    "properties": {"drone_id": {"type": "string"}},
}

TOGGLE_DRONE_PASSIVE_SONAR = {
    "type": "object",
    "required": ["drone_id"],
    "properties": {"drone_id": {"type": "string"}},
}

DETONATE = {
    "type": "object",
    "required": ["drone_id"],
    "properties": {"drone_id": {"type": "string"}},
}

TOGGLE_EMP_PULSE = {
    "type": "object",
    "required": ["drone_id"],
    "properties": {
        "drone_id": {"type": "string"},
        "on": {
            "type": ["boolean", "null"],
            "description": "true=enable, false=disable, null=toggle. EMP drones only.",
        },
    },
}

TOGGLE_DETECTION = {
    "type": "object",
    "required": ["drone_id"],
    "properties": {
        "drone_id": {"type": "string"},
        "on": {
            "type": ["boolean", "null"],
            "description": "true=enable, false=disable, null=toggle. Detection drones only.",
        },
    },
}

TOGGLE_DECOY = {
    "type": "object",
    "required": ["drone_id"],
    "properties": {
        "drone_id": {"type": "string"},
        "on": {
            "type": ["boolean", "null"],
            "description": "true=enable, false=disable, null=toggle. Decoy drones only.",
        },
    },
}

# ── Fueling ───────────────────────────────────────────────────────────────────

CALL_FUELER = {
    "type": "object",
    "required": ["sub_id"],
    "properties": {"sub_id": {"type": "string"}},
}

START_REFUEL = {
    "type": "object",
    "required": ["sub_id"],
    "properties": {"sub_id": {"type": "string"}},
}

# ── Stream ────────────────────────────────────────────────────────────────────

GET_LATEST_SNAPSHOT = {"type": "object", "properties": {}}

GET_EVENT_BUFFER = {
    "type": "object",
    "properties": {
        "event_types": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "Filter by event types: contact, echo, explosion, torpedo_contact, torpedo_ping, emp_pulse, drone_expired. null=all.",
        },
        "limit": {
            "type": "integer",
            "default": 50,
            "description": "Max events to return",
        },
        "since_seconds": {
            "type": ["number", "null"],
            "description": "Only return events from the last N seconds. Use 5-10 for fresh contacts only.",
        },
    },
}

CLEAR_EVENT_BUFFER = {"type": "object", "properties": {}}

GET_SSE_STATUS = {"type": "object", "properties": {}}
