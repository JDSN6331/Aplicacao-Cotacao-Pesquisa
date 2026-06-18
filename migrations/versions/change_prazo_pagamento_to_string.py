"""Alterar campo prazo_pagamento_fornecedor de Date para String

Revision ID: change_prazo_to_string
Revises: 
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'change_prazo_to_string'
down_revision = 'b9f3c2d5e1a6'
branch_labels = None
depends_on = None


def upgrade():
    # Alterar a coluna prazo_pagamento_fornecedor de DATE para VARCHAR
    op.alter_column('produtos_cotacao', 'prazo_pagamento_fornecedor',
                    existing_type=sa.Date(),
                    type_=sa.String(100),
                    existing_nullable=True)


def downgrade():
    # Reverter para DATE em caso de rollback
    op.alter_column('produtos_cotacao', 'prazo_pagamento_fornecedor',
                    existing_type=sa.String(100),
                    type_=sa.Date(),
                    existing_nullable=True)
