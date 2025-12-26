"""Add bookings table

Revision ID: 003_add_bookings
Revises: 002_add_service_packages
Create Date: 2025-12-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

# revision identifiers, used by Alembic.
revision = '003_add_bookings'
down_revision = '002_add_service_packages'
branch_labels = None
depends_on = None


def upgrade():
    # Create bookings table
    op.create_table(
        'bookings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('fan_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('creator_id', UUID(as_uuid=True), sa.ForeignKey('creator_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('service_packages.id', ondelete='CASCADE'), nullable=False),
        
        # Question
        sa.Column('question_video_url', sa.Text, nullable=True),
        sa.Column('question_text', sa.Text, nullable=True),
        sa.Column('question_submitted_at', sa.DateTime(timezone=True), nullable=True),
        
        # Response
        sa.Column('response_media_url', sa.Text, nullable=True),
        sa.Column('response_type', sa.String(20), nullable=True),  # 'voice', 'video'
        sa.Column('response_submitted_at', sa.DateTime(timezone=True), nullable=True),
        
        # Status
        sa.Column('status', sa.String(50), nullable=False, server_default='pending_question'),
        # Status values: 'pending_question', 'awaiting_response', 'completed', 'cancelled'
        sa.Column('payment_status', sa.String(50), nullable=True),
        
        # Pricing
        sa.Column('amount_paid', sa.DECIMAL(10, 2), server_default='0'),
        sa.Column('platform_fee', sa.DECIMAL(10, 2), server_default='0'),
        sa.Column('creator_earnings', sa.DECIMAL(10, 2), server_default='0'),
        
        # SLA tracking
        sa.Column('expected_response_by', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sla_met', sa.Boolean, nullable=True),
        
        # Follow-ups
        sa.Column('follow_ups_remaining', sa.Integer, server_default='0'),
        
        # Ratings
        sa.Column('fan_rating', sa.Integer, nullable=True),
        sa.Column('fan_review', sa.Text, nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create indexes
    op.create_index('idx_bookings_fan', 'bookings', ['fan_id'])
    op.create_index('idx_bookings_creator', 'bookings', ['creator_id'])
    op.create_index('idx_bookings_status', 'bookings', ['status'])
    op.create_index('idx_bookings_created', 'bookings', ['created_at'])


def downgrade():
    op.drop_index('idx_bookings_created', table_name='bookings')
    op.drop_index('idx_bookings_status', table_name='bookings')
    op.drop_index('idx_bookings_creator', table_name='bookings')
    op.drop_index('idx_bookings_fan', table_name='bookings')
    op.drop_table('bookings')
