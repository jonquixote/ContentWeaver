def require_fields(data, fields):
    if not isinstance(data, dict):
        raise ValueError('Request body must be a JSON object')
    missing = [f for f in fields if not data.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
