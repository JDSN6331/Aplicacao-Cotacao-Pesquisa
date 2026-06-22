"""Add ProdutoPesquisa table for multiple products in pesquisas

Revision ID: add_produtos_pesquisa_001
Revises: change_prazo_to_string
Create Date: 2026-06-19 

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_produtos_pesquisa_001'
down_revision = 'change_prazo_to_string'
branch_labels = None
depends_on = None


def upgrade():
    # Create produtos_pesquisa table
    op.create_table(
        'produtos_pesquisa',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pesquisa_id', sa.Integer(), nullable=False),
        sa.Column('codigo_produto', sa.String(100), nullable=True),
        sa.Column('nome_produto', sa.String(100), nullable=False),
        sa.Column('quantidade_cotada', sa.Float(), nullable=False),
        sa.Column('valor_concorrente', sa.Float(), nullable=False),
        sa.Column('valor_cooxupe', sa.Float(), nullable=True),
        sa.Column('fornecedor', sa.String(100), nullable=True),
        sa.Column('nome_concorrente', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pesquisa_id'], ['pesquisas_mercado.id'], )
    )
    
    # Create index on pesquisa_id for faster queries
    op.create_index(op.f('ix_produtos_pesquisa_pesquisa_id'), 'produtos_pesquisa', ['pesquisa_id'], unique=False)


def downgrade():
    # Drop the table
    op.drop_index(op.f('ix_produtos_pesquisa_pesquisa_id'), table_name='produtos_pesquisa')
    op.drop_table('produtos_pesquisa')
