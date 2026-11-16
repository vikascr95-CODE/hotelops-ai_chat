from .schemas import GuestIntent

DEPARTMENT_MAP = {
    "housekeeping": "Housekeeping",
    "maintenance": "Maintenance",
    "reservations": "Reservations",
    "room_service": "Room Service",
    "front_office": "Front Office",
    "concierge": "Concierge",
    "accounts": "Accounts",
    "security": "Security",
    "other": "Other",
}

def route_intent(intent: GuestIntent) -> str:
    """Map validated intent types to an allowlisted hotel department."""
    return DEPARTMENT_MAP[intent.intent_type]
