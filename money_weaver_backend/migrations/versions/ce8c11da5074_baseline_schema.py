"""baseline schema

Revision ID: ce8c11da5074
Revises:
Create Date: 2026-08-17 21:10:16.463315

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'ce8c11da5074'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _if_not_exists(ddl: str) -> str:
    """Inject IF NOT EXISTS after the CREATE prefix of a raw DDL statement.

    sqlite strips the IF NOT EXISTS clause from sqlite_master.sql, so running
    the same DDL against an already-populated database is a no-op (no data
    loss) while freshly-created tables keep byte-identical stored DDL.
    """
    for kw in ('CREATE UNIQUE INDEX ', 'CREATE INDEX ', 'CREATE TABLE '):
        if ddl.startswith(kw):
            return kw + 'IF NOT EXISTS ' + ddl[len(kw):]
    raise ValueError('unhandled DDL: %r' % ddl[:40])


def upgrade() -> None:
    """Upgrade schema.

    Baseline snapshot. The DDL below is copied verbatim from the live
    src/database/app.db (sqlite_master.sql), so:
    - a fresh database gets byte-identical stored DDL (column order, the
      ALTER-appended trailing columns voice_type / thumbnail_path, defaults,
      and index/constraint naming all match the live DB);
    - an existing database is left untouched (IF NOT EXISTS makes every
      statement a no-op), so no data is lost.
    """
    op.execute(_if_not_exists("CREATE TABLE user (\n"
        "\tid INTEGER NOT NULL, \n"
        "\tusername VARCHAR(80) NOT NULL, \n"
        "\temail VARCHAR(120) NOT NULL, \n"
        "\tpassword_hash VARCHAR(120) NOT NULL, \n"
        "\tcreated_at DATETIME, \n"
        "\tupdated_at DATETIME, \n"
        "\tPRIMARY KEY (id), \n"
        "\tUNIQUE (username), \n"
        "\tUNIQUE (email)\n"
        ")"))
    op.execute(_if_not_exists("CREATE TABLE project (\n"
        "\tid INTEGER NOT NULL, \n"
        "\ttitle VARCHAR(200) NOT NULL, \n"
        "\tdescription TEXT, \n"
        "\tuser_id INTEGER NOT NULL, \n"
        "\tstatus VARCHAR(50), \n"
        "\tworkflow_type VARCHAR(50), \n"
        "\tscript TEXT, \n"
        "\tvideo_url VARCHAR(500), \n"
        "\tcreated_at DATETIME, \n"
        "\tupdated_at DATETIME, voice_type VARCHAR(50) DEFAULT 'female', \n"
        "\tPRIMARY KEY (id), \n"
        "\tFOREIGN KEY(user_id) REFERENCES user (id)\n"
        ")"))
    op.execute(_if_not_exists("CREATE TABLE api_key (\n"
        "\tid INTEGER NOT NULL, \n"
        "\tuser_id INTEGER NOT NULL, \n"
        "\tname VARCHAR(100) NOT NULL, \n"
        "\tprovider VARCHAR(50) NOT NULL, \n"
        "\t\"key\" TEXT NOT NULL, \n"
        "\tis_active BOOLEAN, \n"
        "\tcreated_at DATETIME, \n"
        "\tupdated_at DATETIME, \n"
        "\tPRIMARY KEY (id), \n"
        "\tFOREIGN KEY(user_id) REFERENCES user (id)\n"
        ")"))
    op.execute(_if_not_exists("CREATE TABLE task (\n"
        "\tid INTEGER NOT NULL, \n"
        "\tproject_id INTEGER NOT NULL, \n"
        "\ttask_type VARCHAR(100) NOT NULL, \n"
        "\tstatus VARCHAR(50), \n"
        "\tprogress INTEGER, \n"
        "\tresult TEXT, \n"
        "\terror_message TEXT, \n"
        "\tcelery_task_id VARCHAR(255), \n"
        "\tcreated_at DATETIME, \n"
        "\tupdated_at DATETIME, thumbnail_path VARCHAR(500), \n"
        "\tPRIMARY KEY (id), \n"
        "\tFOREIGN KEY(project_id) REFERENCES project (id)\n"
        ")"))
    op.execute(_if_not_exists("CREATE TABLE media_asset (\n"
        "\tid INTEGER NOT NULL, \n"
        "\tproject_id INTEGER NOT NULL, \n"
        "\tfilename VARCHAR(255) NOT NULL, \n"
        "\tfile_path VARCHAR(500) NOT NULL, \n"
        "\tfile_type VARCHAR(50) NOT NULL, \n"
        "\tfile_size INTEGER, \n"
        "\tduration FLOAT, \n"
        "\tasset_metadata TEXT, \n"
        "\tcreated_at DATETIME, \n"
        "\tPRIMARY KEY (id), \n"
        "\tFOREIGN KEY(project_id) REFERENCES project (id)\n"
        ")"))
    op.execute(_if_not_exists("CREATE TABLE token_blocklist (\n"
        "\tid INTEGER NOT NULL, \n"
        "\tjti VARCHAR(36) NOT NULL, \n"
        "\tcreated_at DATETIME, \n"
        "\tPRIMARY KEY (id)\n"
        ")"))
    op.execute(_if_not_exists("CREATE UNIQUE INDEX ix_token_blocklist_jti ON token_blocklist (jti)"))
    op.execute(_if_not_exists("CREATE TABLE format_presets (\n"
        "\tid INTEGER NOT NULL, \n"
        "\tname VARCHAR(50) NOT NULL, \n"
        "\tplatform VARCHAR(50) NOT NULL, \n"
        "\twidth INTEGER NOT NULL, \n"
        "\theight INTEGER NOT NULL, \n"
        "\tfps INTEGER NOT NULL, \n"
        "\tduration_min INTEGER NOT NULL, \n"
        "\tduration_max INTEGER NOT NULL, \n"
        "\tis_default BOOLEAN, \n"
        "\tPRIMARY KEY (id), \n"
        "\tUNIQUE (name)\n"
        ")"))
    op.execute(_if_not_exists("CREATE TABLE video_templates (\n"
        "\tid INTEGER NOT NULL, \n"
        "\tuser_id INTEGER NOT NULL, \n"
        "\tname VARCHAR(100) NOT NULL, \n"
        "\tdescription TEXT, \n"
        "\tconfig JSON NOT NULL, \n"
        "\tis_public BOOLEAN, \n"
        "\tcreated_at DATETIME, \n"
        "\tPRIMARY KEY (id)\n"
        ")"))
    op.execute(_if_not_exists("CREATE TABLE voices (\n"
        "\tid INTEGER NOT NULL, \n"
        "\tuser_id INTEGER NOT NULL, \n"
        "\tname VARCHAR(100) NOT NULL, \n"
        "\treference_audio_url VARCHAR(500) NOT NULL, \n"
        "\tdescription VARCHAR(300), \n"
        "\tcreated_at DATETIME, \n"
        "\tconsent_confirmed_at DATETIME, \n"
        "\tlast_used_at DATETIME, \n"
        "\tPRIMARY KEY (id)\n"
        ")"))
    op.execute(_if_not_exists("CREATE INDEX ix_voices_user_id ON voices (user_id)"))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('DROP INDEX IF EXISTS ix_voices_user_id')
    op.execute('DROP TABLE IF EXISTS voices')
    op.execute('DROP TABLE IF EXISTS video_templates')
    op.execute('DROP TABLE IF EXISTS format_presets')
    op.execute('DROP INDEX IF EXISTS ix_token_blocklist_jti')
    op.execute('DROP TABLE IF EXISTS token_blocklist')
    op.execute('DROP TABLE IF EXISTS media_asset')
    op.execute('DROP TABLE IF EXISTS task')
    op.execute('DROP TABLE IF EXISTS api_key')
    op.execute('DROP TABLE IF EXISTS project')
    op.execute('DROP TABLE IF EXISTS user')