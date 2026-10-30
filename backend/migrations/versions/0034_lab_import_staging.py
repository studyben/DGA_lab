"""Private laboratory evidence staging, separate from all formal business records."""
from alembic import op

revision = '0034_lab_import_staging'
down_revision = '0033_lab_finalization_facts'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE laboratory_source_labs(
        id uuid PRIMARY KEY, display_name varchar(200) NOT NULL CHECK(length(display_name) BETWEEN 1 AND 200),
        name_key varchar(600) NOT NULL, source_kind varchar(20) NOT NULL CHECK(source_kind IN('IN_HOUSE','THIRD_PARTY')),
        created_by uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL);
    CREATE INDEX laboratory_source_labs_name ON laboratory_source_labs(name_key);
    CREATE TABLE lab_import_batches(
        id uuid PRIMARY KEY, format_version smallint NOT NULL CHECK(format_version=1),
        input_format varchar(12) NOT NULL CHECK(input_format IN('XLSX','CSV_PAIR')),
        purpose varchar(12) NOT NULL CHECK(purpose IN('HISTORICAL','DAILY')),
        capture_channel varchar(8) NOT NULL DEFAULT 'BULK' CHECK(capture_channel='BULK'),
        source_timezone varchar(100), source_timezone_confirmed boolean NOT NULL DEFAULT false,
        revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0), validated_revision bigint,
        validation_state varchar(16) NOT NULL DEFAULT 'NOT_REQUESTED'
            CHECK(validation_state IN('NOT_REQUESTED','QUEUED','RUNNING','COMPLETE','FAILED')),
        business_state varchar(8) NOT NULL DEFAULT 'STAGED' CHECK(business_state='STAGED'),
        current_job_id uuid, summary jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(summary)='object'),
        created_by uuid NOT NULL REFERENCES users(id), updated_by uuid NOT NULL REFERENCES users(id),
        created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
        CHECK(validated_revision IS NULL OR validated_revision<=revision),
        CHECK(NOT source_timezone_confirmed OR source_timezone IS NOT NULL));
    CREATE INDEX lab_import_batches_created ON lab_import_batches(created_at DESC,id);
    CREATE INDEX lab_import_batches_filters ON lab_import_batches(purpose,validation_state,created_by);
    CREATE TABLE lab_import_lab_bindings(
        batch_id uuid NOT NULL REFERENCES lab_import_batches(id), source_lab_key varchar(80) NOT NULL,
        source_lab_id uuid NOT NULL REFERENCES laboratory_source_labs(id),
        confirmed_by uuid NOT NULL REFERENCES users(id), confirmed_at timestamptz NOT NULL,
        reason varchar(1000) NOT NULL CHECK(length(reason) BETWEEN 1 AND 1000),
        PRIMARY KEY(batch_id,source_lab_key));
    CREATE INDEX lab_import_lab_bindings_source ON lab_import_lab_bindings(source_lab_id,batch_id);
    CREATE TABLE lab_import_operations(
        id uuid PRIMARY KEY, actor_id uuid NOT NULL REFERENCES users(id), operation_key uuid NOT NULL,
        action varchar(16) NOT NULL CHECK(action IN('CREATE','RECEIVE','REVISE','VALIDATE')),
        batch_id uuid REFERENCES lab_import_batches(id), request_digest char(64) NOT NULL,
        state varchar(12) NOT NULL CHECK(state IN('PENDING','RETRYABLE','COMPLETED','REJECTED')),
        request_snapshot jsonb NOT NULL CHECK(jsonb_typeof(request_snapshot)='object'),
        result jsonb, file_id uuid, lease_token uuid, lease_expires_at timestamptz, error_code varchar(80),
        created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
        UNIQUE(actor_id,operation_key),
        CHECK(state NOT IN('COMPLETED','REJECTED') OR jsonb_typeof(result)='object'));
    CREATE INDEX lab_import_operations_batch ON lab_import_operations(batch_id);
    CREATE TABLE lab_import_files(
        id uuid PRIMARY KEY, batch_id uuid NOT NULL REFERENCES lab_import_batches(id),
        role varchar(10) NOT NULL CHECK(role IN('WORKBOOK','SAMPLES','TESTS')),
        state varchar(12) NOT NULL CHECK(state IN('PENDING','RECEIVED','RETRYABLE')),
        active boolean NOT NULL DEFAULT false, filename varchar(255) NOT NULL, content_type varchar(160) NOT NULL,
        byte_size bigint NOT NULL CHECK(byte_size BETWEEN 1 AND 10485760), sha256 char(64) NOT NULL,
        object_key varchar(500) UNIQUE NOT NULL, operation_id uuid NOT NULL REFERENCES lab_import_operations(id),
        received_by uuid NOT NULL REFERENCES users(id), reserved_at timestamptz NOT NULL,
        received_at timestamptz, failure_code varchar(80), CHECK(NOT active OR state='RECEIVED'));
    ALTER TABLE lab_import_operations ADD FOREIGN KEY(file_id) REFERENCES lab_import_files(id);
    CREATE UNIQUE INDEX lab_import_files_active_role ON lab_import_files(batch_id,role) WHERE active;
    CREATE INDEX lab_import_files_batch ON lab_import_files(batch_id,state);
    CREATE TABLE lab_import_revisions(
        id uuid PRIMARY KEY, batch_id uuid NOT NULL REFERENCES lab_import_batches(id), revision bigint NOT NULL CHECK(revision>0),
        actor_id uuid NOT NULL REFERENCES users(id), occurred_at timestamptz NOT NULL,
        reason varchar(1000) NOT NULL CHECK(length(reason) BETWEEN 1 AND 1000),
        before_value jsonb NOT NULL, after_value jsonb NOT NULL, UNIQUE(batch_id,revision));
    CREATE INDEX lab_import_revisions_batch ON lab_import_revisions(batch_id,revision DESC);
    CREATE TABLE lab_import_rows(
        id uuid PRIMARY KEY, file_id uuid NOT NULL REFERENCES lab_import_files(id),
        batch_id uuid NOT NULL REFERENCES lab_import_batches(id),
        sheet varchar(20) NOT NULL CHECK(sheet IN('油样信息','检测结果')), row_number integer NOT NULL CHECK(row_number>=2),
        raw_values jsonb NOT NULL CHECK(jsonb_typeof(raw_values)='object'),
        raw_cell_types jsonb NOT NULL CHECK(jsonb_typeof(raw_cell_types)='object'),
        overrides jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(overrides)='object'),
        parsed_values jsonb, issues jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(issues)='array'),
        parsed_revision bigint, sample_row_id uuid REFERENCES lab_import_rows(id),
        source_lab_id uuid REFERENCES laboratory_source_labs(id), external_sample_id varchar(160), external_test_id varchar(160),
        UNIQUE(file_id,sheet,row_number));
    CREATE INDEX lab_import_rows_batch ON lab_import_rows(batch_id,sheet,parsed_revision,row_number,id);
    CREATE INDEX lab_import_rows_sample ON lab_import_rows(sample_row_id,row_number,id);
    CREATE TABLE lab_import_jobs(
        id uuid PRIMARY KEY, batch_id uuid NOT NULL REFERENCES lab_import_batches(id), input_revision bigint NOT NULL,
        manifest_digest char(64) NOT NULL, input_snapshot jsonb NOT NULL, request_actor jsonb NOT NULL,
        requested_by uuid NOT NULL REFERENCES users(id),
        state varchar(16) NOT NULL CHECK(state IN('QUEUED','RUNNING','COMPLETE','FAILED','SUPERSEDED')),
        phase varchar(16) NOT NULL CHECK(phase IN('QUEUED','READING','PARSING','VALIDATING','PERSISTING','DONE')),
        progress_done integer NOT NULL DEFAULT 0 CHECK(progress_done>=0),
        progress_total integer NOT NULL DEFAULT 0 CHECK(progress_total>=0),
        claim_token uuid, worker_id varchar(100), lease_expires_at timestamptz,
        attempt integer NOT NULL DEFAULT 0 CHECK(attempt>=0), error_code varchar(80),
        file_issues jsonb NOT NULL DEFAULT '[]'::jsonb, validation_context jsonb NOT NULL DEFAULT '{}'::jsonb,
        created_at timestamptz NOT NULL, started_at timestamptz, completed_at timestamptz);
    ALTER TABLE lab_import_batches ADD FOREIGN KEY(current_job_id) REFERENCES lab_import_jobs(id);
    CREATE UNIQUE INDEX lab_import_jobs_active ON lab_import_jobs(batch_id) WHERE state IN('QUEUED','RUNNING');
    CREATE INDEX lab_import_jobs_claim ON lab_import_jobs(state,lease_expires_at,created_at,id);
    CREATE FUNCTION guard_lab_import_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Laboratory source evidence is immutable'; END $$;
    CREATE TRIGGER laboratory_source_labs_immutable BEFORE UPDATE OR DELETE ON laboratory_source_labs
        FOR EACH ROW EXECUTE FUNCTION guard_lab_import_immutable();
    CREATE TRIGGER lab_import_revisions_immutable BEFORE UPDATE OR DELETE ON lab_import_revisions
        FOR EACH ROW EXECUTE FUNCTION guard_lab_import_immutable();
    CREATE FUNCTION guard_lab_import_file_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP='DELETE' OR (to_jsonb(OLD)-ARRAY['state','active','received_at','failure_code'])
             IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['state','active','received_at','failure_code'])
        THEN RAISE EXCEPTION 'Laboratory original identity is immutable'; END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER lab_import_file_identity BEFORE UPDATE OR DELETE ON lab_import_files
        FOR EACH ROW EXECUTE FUNCTION guard_lab_import_file_identity();
    CREATE FUNCTION guard_lab_import_raw_row() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP='DELETE' OR
           (OLD.id,OLD.file_id,OLD.batch_id,OLD.sheet,OLD.row_number,OLD.raw_values,OLD.raw_cell_types)
           IS DISTINCT FROM (NEW.id,NEW.file_id,NEW.batch_id,NEW.sheet,NEW.row_number,NEW.raw_values,NEW.raw_cell_types)
        THEN RAISE EXCEPTION 'Laboratory raw row is immutable'; END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER lab_import_raw_row BEFORE UPDATE OR DELETE ON lab_import_rows
        FOR EACH ROW EXECUTE FUNCTION guard_lab_import_raw_row();
    """)


def downgrade():
    op.execute("""
    DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM laboratory_source_labs) OR EXISTS(SELECT 1 FROM lab_import_batches)
          OR EXISTS(SELECT 1 FROM lab_import_operations)
        THEN RAISE EXCEPTION 'Retained laboratory imports require forward recovery'; END IF;
    END $$;
    ALTER TABLE lab_import_batches DROP CONSTRAINT lab_import_batches_current_job_id_fkey;
    ALTER TABLE lab_import_operations DROP CONSTRAINT lab_import_operations_file_id_fkey;
    DROP TABLE lab_import_jobs,lab_import_rows,lab_import_revisions,lab_import_files,
        lab_import_operations,lab_import_lab_bindings,lab_import_batches,laboratory_source_labs;
    DROP FUNCTION guard_lab_import_raw_row(),guard_lab_import_file_identity(),guard_lab_import_immutable();
    """)

