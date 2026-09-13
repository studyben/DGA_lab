"""Current barcode report request and immutable finalization snapshot."""

from alembic import op


revision = '0007_laboratory_reports'
down_revision = '0006_laboratory_finalization'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE oil_samples
            ADD COLUMN testing_finalization_token UUID;

        CREATE TABLE laboratory_reports (
            id UUID PRIMARY KEY,
            oil_sample_id UUID NOT NULL UNIQUE REFERENCES oil_samples(id) ON DELETE CASCADE,
            finalization_token UUID NOT NULL,
            generation_token UUID NOT NULL,
            snapshot_schema_version SMALLINT NOT NULL DEFAULT 1
                CHECK (snapshot_schema_version = 1),
            report_snapshot JSONB NOT NULL,
            state VARCHAR(16) NOT NULL
                CHECK (state IN ('QUEUED','GENERATING','READY','FAILED')),
            claim_token UUID,
            lease_expires_at TIMESTAMPTZ,
            object_key TEXT,
            content_sha256 CHAR(64),
            byte_size BIGINT CHECK (byte_size >= 0),
            error_code VARCHAR(80),
            requested_by UUID NOT NULL REFERENCES users(id),
            requested_at TIMESTAMPTZ NOT NULL,
            started_at TIMESTAMPTZ,
            generated_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT laboratory_report_ready_file_consistent CHECK (
                (state = 'READY' AND object_key IS NOT NULL
                    AND content_sha256 IS NOT NULL AND byte_size IS NOT NULL
                    AND generated_at IS NOT NULL)
                OR
                (state <> 'READY' AND object_key IS NULL
                    AND content_sha256 IS NULL AND byte_size IS NULL
                    AND generated_at IS NULL)
            ),
            CONSTRAINT laboratory_report_error_consistent CHECK (
                (state = 'FAILED' AND error_code IS NOT NULL)
                OR (state <> 'FAILED' AND error_code IS NULL)
            )
        );
        CREATE INDEX laboratory_reports_worker_queue
            ON laboratory_reports(state,lease_expires_at,requested_at);
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE laboratory_reports;
        ALTER TABLE oil_samples DROP COLUMN testing_finalization_token;
        """
    )
