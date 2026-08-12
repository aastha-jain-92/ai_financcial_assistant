"""Google OAuth token metadata and one-time oauth_states

Revision ID: b1c4d7e9a205
Revises: cfea6245742a
Create Date: 2026-08-12 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c4d7e9a205'
down_revision: Union[str, Sequence[str], None] = 'cfea6245742a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'user_integrations',
        'access_token',
        existing_type=sa.String(length=512),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        'user_integrations',
        'refresh_token',
        existing_type=sa.String(length=512),
        type_=sa.Text(),
        existing_nullable=True,
    )

    op.add_column(
        'user_integrations',
        sa.Column(
            'token_expires_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        'user_integrations',
        sa.Column('scopes', sa.Text(), nullable=True),
    )
    op.add_column(
        'user_integrations',
        sa.Column('google_email', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'user_integrations',
        sa.Column('last_error', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'user_integrations',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )

    # Collapse pre-existing duplicates so the unique constraint applies.
    op.execute(
        """
        DELETE FROM user_integrations a
        USING user_integrations b
        WHERE a.user_id = b.user_id
          AND a.service_name = b.service_name
          AND a.id < b.id
        """
    )

    op.create_unique_constraint(
        'uq_user_integration_service',
        'user_integrations',
        ['user_id', 'service_name'],
    )

    op.create_table(
        'oauth_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=128), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('service_name', sa.String(length=50), nullable=False),
        sa.Column('telegram_chat_id', sa.String(length=64), nullable=True),
        sa.Column(
            'expires_at',
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            'consumed_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_oauth_states_id'), 'oauth_states', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_oauth_states_state'),
        'oauth_states',
        ['state'],
        unique=True,
    )
    op.create_index(
        op.f('ix_oauth_states_user_id'),
        'oauth_states',
        ['user_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_oauth_states_user_id'), table_name='oauth_states')
    op.drop_index(op.f('ix_oauth_states_state'), table_name='oauth_states')
    op.drop_index(op.f('ix_oauth_states_id'), table_name='oauth_states')
    op.drop_table('oauth_states')

    op.drop_constraint(
        'uq_user_integration_service',
        'user_integrations',
        type_='unique',
    )

    op.drop_column('user_integrations', 'updated_at')
    op.drop_column('user_integrations', 'last_error')
    op.drop_column('user_integrations', 'google_email')
    op.drop_column('user_integrations', 'scopes')
    op.drop_column('user_integrations', 'token_expires_at')

    op.alter_column(
        'user_integrations',
        'refresh_token',
        existing_type=sa.Text(),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
    op.alter_column(
        'user_integrations',
        'access_token',
        existing_type=sa.Text(),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
