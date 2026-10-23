"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-23 23:32:04.469461
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table('components',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('manufacturer', sa.String(length=120), nullable=False),
    sa.Column('model', sa.String(length=160), nullable=False),
    sa.Column('specs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('price_sar', sa.Float(), nullable=False),
    sa.Column('price_unit', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_components_kind'), 'components', ['kind'], unique=False)
    op.create_table('price_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=False),
    sa.Column('unit_price_sar', sa.Float(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tariffs',
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('tiers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('vat', sa.Float(), nullable=False),
    sa.Column('export_rate_sar', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=False),
    sa.Column('password_hash', sa.String(length=200), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('weather_cache',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('latitude', 'longitude', 'source')
    )
    op.create_table('customers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('phone', sa.String(length=40), nullable=True),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('customer_type', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_name'), 'customers', ['name'], unique=False)
    op.create_geospatial_table('projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('location', Geometry(geometry_type='POINT', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('address', sa.String(length=300), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('monthly_consumption_kwh', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('tariff_code', sa.String(length=30), nullable=False),
    sa.Column('designer_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.ForeignKeyConstraint(['designer_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_geospatial_index('idx_projects_location', 'projects', ['location'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_index(op.f('ix_projects_customer_id'), 'projects', ['customer_id'], unique=False)
    op.create_index(op.f('ix_projects_name'), 'projects', ['name'], unique=False)
    op.create_index(op.f('ix_projects_status'), 'projects', ['status'], unique=False)
    op.create_table('design_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('inverter_id', sa.Integer(), nullable=True),
    sa.Column('inverter_count', sa.Integer(), nullable=False),
    sa.Column('racking_id', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['inverter_id'], ['components.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['racking_id'], ['components.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'version_no')
    )
    op.create_index(op.f('ix_design_versions_project_id'), 'design_versions', ['project_id'], unique=False)
    op.create_geospatial_table('obstructions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('design_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('geometry', Geometry(geometry_type='POLYGON', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('height_m', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['design_id'], ['design_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_geospatial_index('idx_obstructions_geometry', 'obstructions', ['geometry'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_index(op.f('ix_obstructions_design_id'), 'obstructions', ['design_id'], unique=False)
    op.create_geospatial_table('roof_areas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('design_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('geometry', Geometry(geometry_type='POLYGON', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('height_m', sa.Float(), nullable=False),
    sa.Column('pitch_deg', sa.Float(), nullable=False),
    sa.Column('azimuth_deg', sa.Float(), nullable=False),
    sa.Column('setback_m', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['design_id'], ['design_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_geospatial_index('idx_roof_areas_geometry', 'roof_areas', ['geometry'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_index(op.f('ix_roof_areas_design_id'), 'roof_areas', ['design_id'], unique=False)
    op.create_table('simulations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('design_id', sa.Integer(), nullable=False),
    sa.Column('weather_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('inputs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['design_id'], ['design_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_simulations_design_id'), 'simulations', ['design_id'], unique=False)
    op.create_table('arrays',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('roof_area_id', sa.Integer(), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=False),
    sa.Column('orientation', sa.String(length=12), nullable=False),
    sa.Column('mounting', sa.String(length=16), nullable=False),
    sa.Column('tilt_deg', sa.Float(), nullable=False),
    sa.Column('azimuth_deg', sa.Float(), nullable=False),
    sa.Column('row_spacing_m', sa.Float(), nullable=False),
    sa.Column('module_gap_m', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['module_id'], ['components.id'], ),
    sa.ForeignKeyConstraint(['roof_area_id'], ['roof_areas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_arrays_roof_area_id'), 'arrays', ['roof_area_id'], unique=False)
    op.create_table('reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('simulation_id', sa.Integer(), nullable=False),
    sa.Column('language', sa.String(length=5), nullable=False),
    sa.Column('pdf', sa.LargeBinary(), nullable=False),
    sa.Column('quote', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('financial', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['simulation_id'], ['simulations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_simulation_id'), 'reports', ['simulation_id'], unique=False)
    op.create_geospatial_table('modules_layout',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('array_id', sa.Integer(), nullable=False),
    sa.Column('position', Geometry(geometry_type='POINT', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('x', sa.Float(), nullable=False),
    sa.Column('y', sa.Float(), nullable=False),
    sa.Column('z', sa.Float(), nullable=False),
    sa.Column('rotation_deg', sa.Float(), nullable=False),
    sa.Column('string_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['array_id'], ['arrays.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_geospatial_index('idx_modules_layout_position', 'modules_layout', ['position'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_index(op.f('ix_modules_layout_array_id'), 'modules_layout', ['array_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_modules_layout_array_id'), table_name='modules_layout')
    op.drop_geospatial_index('idx_modules_layout_position', table_name='modules_layout', postgresql_using='gist', column_name='position')
    op.drop_geospatial_table('modules_layout')
    op.drop_index(op.f('ix_reports_simulation_id'), table_name='reports')
    op.drop_table('reports')
    op.drop_index(op.f('ix_arrays_roof_area_id'), table_name='arrays')
    op.drop_table('arrays')
    op.drop_index(op.f('ix_simulations_design_id'), table_name='simulations')
    op.drop_table('simulations')
    op.drop_index(op.f('ix_roof_areas_design_id'), table_name='roof_areas')
    op.drop_geospatial_index('idx_roof_areas_geometry', table_name='roof_areas', postgresql_using='gist', column_name='geometry')
    op.drop_geospatial_table('roof_areas')
    op.drop_index(op.f('ix_obstructions_design_id'), table_name='obstructions')
    op.drop_geospatial_index('idx_obstructions_geometry', table_name='obstructions', postgresql_using='gist', column_name='geometry')
    op.drop_geospatial_table('obstructions')
    op.drop_index(op.f('ix_design_versions_project_id'), table_name='design_versions')
    op.drop_table('design_versions')
    op.drop_index(op.f('ix_projects_status'), table_name='projects')
    op.drop_index(op.f('ix_projects_name'), table_name='projects')
    op.drop_index(op.f('ix_projects_customer_id'), table_name='projects')
    op.drop_geospatial_index('idx_projects_location', table_name='projects', postgresql_using='gist', column_name='location')
    op.drop_geospatial_table('projects')
    op.drop_index(op.f('ix_customers_name'), table_name='customers')
    op.drop_table('customers')
    op.drop_table('weather_cache')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('tariffs')
    op.drop_table('price_items')
    op.drop_index(op.f('ix_components_kind'), table_name='components')
    op.drop_table('components')
