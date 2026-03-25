ROLE_PERMISSIONS: dict[str, list[str]] = {
    "finance": ["finance", "general"],
    "marketing": ["marketing", "general"],
    "hr": ["hr", "general"],
    "engineering": ["engineering", "general"],
    "c_level": ["finance", "marketing", "hr", "engineering", "general"],
    "employee": ["general"],
}


def get_allowed_departments(role: str) -> list[str]:
    """Return the list of permitted department tags for a given role."""
    return ROLE_PERMISSIONS.get(role, [])
