def test_project_has_studio_state_columns():
    from src.models.project import Project
    cols = {c.name for c in Project.__table__.columns}
    assert 'studio_state' in cols
    assert 'schema_version' in cols