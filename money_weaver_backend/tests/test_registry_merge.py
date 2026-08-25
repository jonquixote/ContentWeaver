def test_list_models_includes_fal_catalog(monkeypatch):
    from src.services.providers import registry as reg_mod
    from src.services.providers.fal_adapter import FAL_CATALOG
    monkeypatch.setattr(reg_mod.registry, '_cache', None)
    monkeypatch.setattr(reg_mod.registry, '_fetched_at', 0.0)
    monkeypatch.setattr(reg_mod, 'EXTRA_CATALOG_SOURCES', [
        lambda: FAL_CATALOG,
        lambda: (_ for _ in ()).throw(RuntimeError("down")),
    ])
    models = reg_mod.registry.list_models(force=True)
    ids = {m['id'] for m in models}
    assert 'fal-ai/wan-t2v' in ids


def test_adding_fal_key_invalidates_cache(client, auth_headers, monkeypatch):
    from fastapi_app.routers import api_keys
    from src.services.providers import registry as reg_mod
    warmed = {}
    monkeypatch.setattr(api_keys, 'warm_provider_catalogs',
                        lambda: warmed.setdefault('called', True))
    r = client.post('/api/api-keys', headers=auth_headers,
                    json={'name': 'FAL', 'provider': 'fal', 'key': 'fake-fal-key'})
    assert r.status_code == 201
    assert warmed.get('called') is True


def test_fal_registration_idempotent():
    """Importing fal_adapter must not duplicate its catalog source."""
    import importlib
    from src.services.providers import fal_adapter, registry as reg_mod
    before = sum(1 for s in reg_mod.EXTRA_CATALOG_SOURCES
                 if getattr(s, '__name__', '') == 'catalog_models')
    importlib.reload(fal_adapter)
    after = sum(1 for s in reg_mod.EXTRA_CATALOG_SOURCES
                if getattr(s, '__name__', '') == 'catalog_models')
    assert before >= 1
    assert after == before
