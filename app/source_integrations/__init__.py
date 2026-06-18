def get_integration(source):
    from app.source_integrations.registry import get_integration as _get_integration

    return _get_integration(source)
