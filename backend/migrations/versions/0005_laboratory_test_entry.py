"""Typed laboratory test entry and object metadata."""

from alembic import op


revision = '0005_laboratory_test_entry'
down_revision = '0004_laboratory_reception'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE oil_samples
            ADD COLUMN testing_status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
                CHECK (testing_status IN ('OPEN','FINALIZED')),
            ADD COLUMN updated_by UUID REFERENCES users(id),
            ADD COLUMN updated_at TIMESTAMPTZ;

        CREATE TABLE test_method_versions (
            id UUID PRIMARY KEY,
            test_type VARCHAR(30) NOT NULL
                CHECK (test_type IN ('DGA','MOISTURE','BREAKDOWN_VOLTAGE')),
            display_name VARCHAR(160) NOT NULL,
            standard_reference VARCHAR(160),
            version_label VARCHAR(80) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE (test_type,version_label)
        );
        CREATE TABLE test_method_fields (
            method_version_id UUID NOT NULL REFERENCES test_method_versions(id),
            field_code VARCHAR(30) NOT NULL,
            display_name VARCHAR(80) NOT NULL,
            unit_code VARCHAR(40),
            display_decimal_places SMALLINT CHECK (display_decimal_places BETWEEN 0 AND 6),
            detection_limit NUMERIC(18,6),
            sort_order SMALLINT NOT NULL,
            PRIMARY KEY (method_version_id,field_code)
        );

        INSERT INTO test_method_versions
            (id,test_type,display_name,standard_reference,version_label)
        VALUES
            ('66000000-0000-0000-0000-000000000001','DGA','DGA 方法（待配置）',NULL,'MVP-PLACEHOLDER'),
            ('66000000-0000-0000-0000-000000000002','MOISTURE','微水方法（待配置）',NULL,'MVP-PLACEHOLDER'),
            ('66000000-0000-0000-0000-000000000003','BREAKDOWN_VOLTAGE','击穿电压方法（待配置）',NULL,'MVP-PLACEHOLDER');
        INSERT INTO test_method_fields
            (method_version_id,field_code,display_name,unit_code,display_decimal_places,detection_limit,sort_order)
        VALUES
            ('66000000-0000-0000-0000-000000000001','H2','H₂',NULL,NULL,NULL,1),
            ('66000000-0000-0000-0000-000000000001','CH4','CH₄',NULL,NULL,NULL,2),
            ('66000000-0000-0000-0000-000000000001','C2H2','C₂H₂',NULL,NULL,NULL,3),
            ('66000000-0000-0000-0000-000000000001','C2H4','C₂H₄',NULL,NULL,NULL,4),
            ('66000000-0000-0000-0000-000000000001','C2H6','C₂H₆',NULL,NULL,NULL,5),
            ('66000000-0000-0000-0000-000000000001','CO','CO',NULL,NULL,NULL,6),
            ('66000000-0000-0000-0000-000000000001','CO2','CO₂',NULL,NULL,NULL,7),
            ('66000000-0000-0000-0000-000000000002','MOISTURE','微水',NULL,NULL,NULL,1),
            ('66000000-0000-0000-0000-000000000003','BREAKDOWN_VOLTAGE','击穿电压',NULL,NULL,NULL,1);

        CREATE TABLE laboratory_tests (
            id UUID PRIMARY KEY,
            oil_sample_id UUID NOT NULL REFERENCES oil_samples(id),
            test_type VARCHAR(30) NOT NULL
                CHECK (test_type IN ('DGA','MOISTURE','BREAKDOWN_VOLTAGE')),
            method_version_id UUID NOT NULL REFERENCES test_method_versions(id),
            measured_at TIMESTAMPTZ NOT NULL,
            instrument_name VARCHAR(160),
            analyst_user_id UUID NOT NULL REFERENCES users(id),
            notes VARCHAR(2000),
            record_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                CHECK (record_status IN ('ACTIVE','REMOVED')),
            removal_reason VARCHAR(500),
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL,
            updated_by UUID NOT NULL REFERENCES users(id),
            updated_at TIMESTAMPTZ NOT NULL,
            CHECK ((record_status='ACTIVE' AND removal_reason IS NULL)
                OR (record_status='REMOVED' AND removal_reason IS NOT NULL))
        );
        CREATE INDEX laboratory_tests_sample ON laboratory_tests(oil_sample_id,created_at,id);

        CREATE TABLE dga_test_results (
            test_id UUID PRIMARY KEY REFERENCES laboratory_tests(id),
            h2_value NUMERIC(18,6), h2_qualifier VARCHAR(2) NOT NULL CHECK (h2_qualifier IN ('EQ','ND','LT','GT')),
            ch4_value NUMERIC(18,6), ch4_qualifier VARCHAR(2) NOT NULL CHECK (ch4_qualifier IN ('EQ','ND','LT','GT')),
            c2h2_value NUMERIC(18,6), c2h2_qualifier VARCHAR(2) NOT NULL CHECK (c2h2_qualifier IN ('EQ','ND','LT','GT')),
            c2h4_value NUMERIC(18,6), c2h4_qualifier VARCHAR(2) NOT NULL CHECK (c2h4_qualifier IN ('EQ','ND','LT','GT')),
            c2h6_value NUMERIC(18,6), c2h6_qualifier VARCHAR(2) NOT NULL CHECK (c2h6_qualifier IN ('EQ','ND','LT','GT')),
            co_value NUMERIC(18,6), co_qualifier VARCHAR(2) NOT NULL CHECK (co_qualifier IN ('EQ','ND','LT','GT')),
            co2_value NUMERIC(18,6), co2_qualifier VARCHAR(2) NOT NULL CHECK (co2_qualifier IN ('EQ','ND','LT','GT'))
        );
        CREATE TABLE moisture_test_results (
            test_id UUID PRIMARY KEY REFERENCES laboratory_tests(id),
            result_value NUMERIC(18,6),
            result_qualifier VARCHAR(2) NOT NULL CHECK (result_qualifier IN ('EQ','ND','LT','GT'))
        );
        CREATE TABLE breakdown_voltage_test_results (
            test_id UUID PRIMARY KEY REFERENCES laboratory_tests(id),
            result_value NUMERIC(18,6),
            result_qualifier VARCHAR(2) NOT NULL CHECK (result_qualifier IN ('EQ','ND','LT','GT'))
        );

        CREATE TABLE stored_objects (
            id UUID PRIMARY KEY,
            object_key VARCHAR(500) UNIQUE NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            content_type VARCHAR(160) NOT NULL,
            byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
            sha256_hex CHAR(64) NOT NULL,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL
        );
        CREATE TABLE laboratory_test_attachments (
            test_id UUID NOT NULL REFERENCES laboratory_tests(id),
            stored_object_id UUID NOT NULL REFERENCES stored_objects(id),
            PRIMARY KEY (test_id,stored_object_id)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE laboratory_test_attachments,stored_objects,
            breakdown_voltage_test_results,moisture_test_results,dga_test_results,
            laboratory_tests,test_method_fields,test_method_versions;
        ALTER TABLE oil_samples DROP COLUMN updated_at,DROP COLUMN updated_by,DROP COLUMN testing_status;
        """
    )
