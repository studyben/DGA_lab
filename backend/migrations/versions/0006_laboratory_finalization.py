"""Overall testing finalization and report-result selection."""

from alembic import op


revision = '0006_laboratory_finalization'
down_revision = '0005_laboratory_test_entry'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE laboratory_tests
            ADD COLUMN selected_for_report BOOLEAN NOT NULL DEFAULT FALSE,
            ADD CONSTRAINT selected_result_must_be_active
                CHECK (NOT selected_for_report OR record_status='ACTIVE');
        CREATE UNIQUE INDEX laboratory_one_selected_result_per_type
            ON laboratory_tests(oil_sample_id,test_type)
            WHERE selected_for_report AND record_status='ACTIVE';

        ALTER TABLE oil_samples
            ADD COLUMN testing_finalized_by UUID REFERENCES users(id),
            ADD COLUMN testing_finalized_at TIMESTAMPTZ,
            ADD CONSTRAINT testing_status_and_finalizer_consistent CHECK (
                (testing_status='OPEN'
                    AND testing_finalized_by IS NULL AND testing_finalized_at IS NULL)
                OR
                (testing_status='FINALIZED'
                    AND testing_finalized_by IS NOT NULL AND testing_finalized_at IS NOT NULL)
            );

        CREATE TABLE laboratory_finalization_events (
            id UUID PRIMARY KEY,
            oil_sample_id UUID NOT NULL REFERENCES oil_samples(id),
            event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('FINALIZED','WITHDRAWN')),
            actor_user_id UUID NOT NULL REFERENCES users(id),
            occurred_at TIMESTAMPTZ NOT NULL,
            reason VARCHAR(500),
            CHECK (
                (event_type='FINALIZED' AND reason IS NULL)
                OR
                (event_type='WITHDRAWN' AND reason IS NOT NULL AND length(btrim(reason)) > 0)
            )
        );
        CREATE INDEX laboratory_finalization_events_sample
            ON laboratory_finalization_events(oil_sample_id,occurred_at,id);
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE laboratory_finalization_events;
        ALTER TABLE oil_samples
            DROP CONSTRAINT testing_status_and_finalizer_consistent,
            DROP COLUMN testing_finalized_at,
            DROP COLUMN testing_finalized_by;
        DROP INDEX laboratory_one_selected_result_per_type;
        ALTER TABLE laboratory_tests
            DROP CONSTRAINT selected_result_must_be_active,
            DROP COLUMN selected_for_report;
        """
    )
