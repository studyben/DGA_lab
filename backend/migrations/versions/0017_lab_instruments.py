"""Instrument and measurement-time quality evidence."""
from alembic import op

revision = '0017_lab_instruments'
down_revision = '0016_lab_configuration'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE laboratory_instruments (
          id UUID PRIMARY KEY, code VARCHAR(40) UNIQUE NOT NULL, name VARCHAR(150) NOT NULL,
          model VARCHAR(150), serial_number VARCHAR(150),
          status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','OUT_OF_SERVICE','RETIRED')),
          created_by UUID NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE laboratory_calibrations (
          id UUID PRIMARY KEY, instrument_id UUID NOT NULL REFERENCES laboratory_instruments(id),
          calibrated_on DATE NOT NULL, expires_on DATE,
          outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('VALID','FAILED','UNKNOWN')),
          provider VARCHAR(150), certificate VARCHAR(100),
          created_by UUID NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(instrument_id,calibrated_on), CHECK (expires_on IS NULL OR expires_on >= calibrated_on)
        );
        CREATE TRIGGER calibration_append_only BEFORE UPDATE OR DELETE ON laboratory_calibrations
          FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
        ALTER TABLE laboratory_tests ADD COLUMN instrument_id UUID REFERENCES laboratory_instruments(id),
          ADD COLUMN quality_snapshot JSONB;
    """)


def downgrade():
    op.execute("""
      DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM laboratory_instruments) OR
           EXISTS (SELECT 1 FROM laboratory_tests WHERE quality_snapshot IS NOT NULL)
        THEN RAISE EXCEPTION 'Retained quality evidence prevents downgrade'; END IF;
      END $$;
      ALTER TABLE laboratory_tests DROP COLUMN instrument_id,DROP COLUMN quality_snapshot;
      DROP TABLE laboratory_calibrations,laboratory_instruments;
    """)
