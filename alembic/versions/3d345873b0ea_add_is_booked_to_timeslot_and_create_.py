"""add is_booked to timeslot and create appointment table

Revision ID: 3d345873b0ea
Revises: 865a8746d1fe
Create Date: 2025-04-11 14:18:05.144546

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite # Import specific dialect if needed, though batch often handles it

# revision identifiers, used by Alembic.
revision: str = '3d345873b0ea'
down_revision: Union[str, None] = '865a8746d1fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### Use Batch Mode for time_slots table modifications ###
    with op.batch_alter_table('time_slots', schema=None) as batch_op:
        # Add the new column with server_default for existing rows
        batch_op.add_column(sa.Column('is_booked', sa.Boolean(), server_default='0', nullable=False))
        # Ensure other columns are NOT NULL (these might be harmlessly redundant if already set)
        batch_op.alter_column('start_time',
               existing_type=sa.VARCHAR(), # Match type detected by alembic
               nullable=False)
        batch_op.alter_column('date',
               existing_type=sa.DATE(), # Match type detected by alembic
               nullable=False)
        batch_op.alter_column('doctor_id',
               existing_type=sa.INTEGER(), # Match type detected by alembic
               nullable=False)
        # Remove the old column
        batch_op.drop_column('day_of_week')
        # Create indices within the batch operation
        batch_op.create_index(batch_op.f('ix_time_slots_date'), ['date'], unique=False)
        batch_op.create_index(batch_op.f('ix_time_slots_is_booked'), ['is_booked'], unique=False)

    # ### Use Batch Mode for users table modifications ###
    with op.batch_alter_table('users', schema=None) as batch_op:
         # Make role NOT NULL
         batch_op.alter_column('role',
                existing_type=sa.VARCHAR(length=7), # Match type/length detected by alembic
                nullable=False)
         # Add index for email (assuming unique=True was added to model)
         batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    # ### Create the new appointments table (can stay outside batch) ###
    op.create_table('appointments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=False),
        sa.Column('timeslot_id', sa.Integer(), nullable=False), # Link to the specific slot
        sa.Column('appointment_date', sa.Date(), nullable=False),
        # Note: Enum needs name specified for SQLite compatibility in some cases
        sa.Column('status', sa.Enum('PENDING', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED', name='appointmentstatus'), server_default='PENDING', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False), # Use server_default
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False), # Use server_default
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], name=op.f('fk_appointments_doctor_id_users')), # Optional: Add names for constraints
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], name=op.f('fk_appointments_patient_id_users')),
        sa.ForeignKeyConstraint(['timeslot_id'], ['time_slots.id'], name=op.f('fk_appointments_timeslot_id_time_slots')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_appointments')),
        sa.UniqueConstraint('timeslot_id', name=op.f('uq_appointments_timeslot_id')) # Ensure one appointment per timeslot
    )
    # Create indices for appointments table
    op.create_index(op.f('ix_appointments_doctor_id'), 'appointments', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_appointments_patient_id'), 'appointments', ['patient_id'], unique=False)
    op.create_index(op.f('ix_appointments_status'), 'appointments', ['status'], unique=False)
    # Index for timeslot_id is implicitly created by UniqueConstraint usually


def downgrade() -> None:
    """Downgrade schema."""
    # ### Drop appointments table and its indices first ###
    op.drop_index(op.f('ix_appointments_status'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_patient_id'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_doctor_id'), table_name='appointments')
    # op.drop_index(op.f('ix_appointments_timeslot_id'), table_name='appointments') # Usually not needed if dropping table/constraint
    op.drop_table('appointments')

    # ### Revert users table changes using Batch Mode ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        # Drop index added in upgrade
        batch_op.drop_index(batch_op.f('ix_users_email'))
        # Revert role nullability (assuming it was nullable before)
        batch_op.alter_column('role',
               existing_type=sa.VARCHAR(length=7),
               nullable=True) # Change back to nullable=True

    # ### Revert time_slots table changes using Batch Mode ###
    with op.batch_alter_table('time_slots', schema=None) as batch_op:
        # Drop indices added in upgrade
        batch_op.drop_index(batch_op.f('ix_time_slots_is_booked'))
        batch_op.drop_index(batch_op.f('ix_time_slots_date'))
        # Add back the old column (assuming it was VARCHAR and nullable)
        batch_op.add_column(sa.Column('day_of_week', sa.VARCHAR(), nullable=True))
        # Revert nullability changes (assuming they were nullable before - adjust if not)
        batch_op.alter_column('doctor_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('date',
               existing_type=sa.DATE(),
               nullable=True)
        batch_op.alter_column('start_time',
               existing_type=sa.VARCHAR(),
               nullable=True)
        # Drop the new column added in upgrade
        batch_op.drop_column('is_booked')