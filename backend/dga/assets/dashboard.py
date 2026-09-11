"""Asset-owned current site read models. No historical sample data is read."""
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text


class DashboardQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_line: Literal['PV', 'ESS'] = 'PV'
    site: str = Field(default='', max_length=200)
    customer: str = Field(default='', max_length=200)
    location: str = Field(default='', max_length=300)
    grid_year: int | None = Field(default=None, ge=1900, le=2200)
    grid_status: Literal['NOT_STARTED', 'IN_PROGRESS', 'COMPLETED'] | None = None
    operation_status: Literal['NOT_OPERATIONAL', 'PARTIAL', 'OPERATIONAL', 'DECOMMISSIONED'] | None = None
    sort: Literal['site_name', 'location_text', 'customer_name', 'power_mw', 'energy_mwh', 'grid_year', 'grid_status', 'operation_status', 'commissioning_date'] = 'site_name'
    direction: Literal['asc', 'desc'] = 'asc'
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=20, ge=1, le=100)


class EquipmentQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(default='', max_length=200)
    product_line: Literal['PV', 'ESS'] = 'PV'
    serial: str = Field(default='', max_length=160)
    model: str = Field(default='', max_length=120)
    machine_type: Literal['INVERTER_UNIT', 'INVERTER', 'ESS_SYSTEM', 'PCS_UNIT', 'PCS', 'BATTERY_CABINET', 'TRANSFORMER'] | None = None
    lifecycle_status: Literal['COMMISSIONING', 'IN_SERVICE', 'OUT_OF_SERVICE', 'RETIRED', 'MERGED'] | None = None
    sort: Literal['display_name', 'system_asset_number', 'serial_number', 'model', 'material_number', 'machine_type', 'lifecycle_status', 'power_mw', 'energy_mwh'] = 'system_asset_number'
    direction: Literal['asc', 'desc'] = 'asc'
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=20, ge=1, le=100)


SITE_CTE = '''WITH RECURSIVE matching_sites AS (
    SELECT s.id,s.site_name,s.location_text,c.id AS customer_id,c.customer_name,
           s.grid_year,s.grid_status,s.operation_status,s.commissioning_date,
           p.product_line,p.power_mw,p.energy_mwh
    FROM sites s JOIN customers c ON c.id=s.customer_id
    JOIN site_product_lines p ON p.site_id=s.id
    WHERE p.product_line=:product_line
      AND position(lower(:site) in lower(s.site_name))>0
      AND position(lower(:customer) in lower(c.customer_name))>0
      AND position(lower(:location) in lower(coalesce(s.location_text,'')))>0
      AND (CAST(:grid_year AS integer) IS NULL OR s.grid_year=:grid_year)
      AND (CAST(:grid_status AS text) IS NULL OR s.grid_status=:grid_status)
      AND (CAST(:operation_status AS text) IS NULL OR s.operation_status=:operation_status)
), current_assets AS (
    SELECT a.id,a.machine_type,a.power_mw,a.energy_mwh,ARRAY[a.id] AS path
    FROM matching_sites s JOIN asset_installations i ON i.site_id=s.id
    JOIN formal_assets a ON a.id=i.asset_id
    WHERE i.valid_from<=:at AND (i.valid_to IS NULL OR i.valid_to>:at)
      AND a.product_line=:product_line AND a.lifecycle_status NOT IN ('RETIRED','MERGED')
    UNION ALL
    SELECT a.id,a.machine_type,a.power_mw,a.energy_mwh,p.path || a.id
    FROM current_assets p JOIN asset_installations i ON i.parent_asset_id=p.id
    JOIN formal_assets a ON a.id=i.asset_id
    WHERE i.valid_from<=:at AND (i.valid_to IS NULL OR i.valid_to>:at)
      AND NOT a.id=ANY(p.path) AND a.lifecycle_status NOT IN ('RETIRED','MERGED')
      AND (a.product_line IS NULL OR a.product_line=:product_line)
) '''


def dashboard(engine, query: DashboardQuery, at):
    params = query.model_dump() | {'at': at, 'offset': (query.page - 1) * query.page_size}
    for field in ('site', 'customer', 'location'):
        params[field] = params[field].strip()
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
        totals = c.execute(text(SITE_CTE + '''SELECT count(*) AS site_count,
            count(DISTINCT customer_id) AS customer_count FROM matching_sites'''), params).mappings().one()
        # Identifiers are constrained by DashboardQuery; user values remain parameters.
        rows = c.execute(text(SITE_CTE + f'''SELECT * FROM matching_sites
            ORDER BY {query.sort} {query.direction} NULLS LAST,id
            LIMIT :page_size OFFSET :offset'''), params).mappings().all()
        machines = c.execute(text(SITE_CTE + '''SELECT machine_type,count(*) AS count,
            sum(power_mw) AS power_mw,sum(energy_mwh) AS energy_mwh,
            count(*)-count(power_mw) AS missing_power_count,
            count(*)-count(energy_mwh) AS missing_energy_count
            FROM (SELECT DISTINCT id,machine_type,power_mw,energy_mwh FROM current_assets) a
            GROUP BY machine_type ORDER BY machine_type NULLS LAST'''), params).mappings().all()
        return dict(totals) | {'product_line': query.product_line, 'page': query.page,
            'page_size': query.page_size, 'sites': [dict(r) for r in rows],
            'machine_totals': [dict(r) for r in machines]}


def site_detail(engine, site_id, query: EquipmentQuery, at):
    params = query.model_dump() | {'site_id': site_id, 'at': at, 'offset': (query.page - 1) * query.page_size}
    params['serial'] = params['serial'].strip()
    params['model'] = params['model'].strip()
    equipment_sql = '''FROM formal_assets a WHERE a.product_line=:product_line
        AND position(lower(:name) in lower(concat_ws(' ',a.tag_number,a.equipment_name,a.system_asset_number)))>0
        AND EXISTS (SELECT 1 FROM asset_installations i WHERE i.asset_id=a.id
            AND i.site_id=:site_id AND i.valid_from<=:at AND (i.valid_to IS NULL OR i.valid_to>:at))
        AND position(lower(:serial) in lower(a.serial_number))>0
        AND position(lower(:model) in lower(coalesce(a.model,'')))>0
        AND (CAST(:machine_type AS text) IS NULL OR a.machine_type=:machine_type)
        AND (CAST(:lifecycle_status AS text) IS NULL OR a.lifecycle_status=:lifecycle_status)'''
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
        site = c.execute(text('''SELECT s.id,s.customer_id,s.site_name,s.location_text,
            s.grid_year,s.grid_status,s.operation_status,s.commissioning_date,
            c.customer_name,p.product_line,p.power_mw,p.energy_mwh
            FROM sites s JOIN customers c ON c.id=s.customer_id
            JOIN site_product_lines p ON p.site_id=s.id
            WHERE s.id=:site_id AND p.product_line=:product_line'''), params).mappings().first()
        if site is None:
            return None
        count = c.execute(text('SELECT count(*) ' + equipment_sql), params).scalar_one()
        rows = c.execute(text('''SELECT a.id,a.system_asset_number,a.serial_number,a.model,
            a.material_number,a.machine_type,a.lifecycle_status,a.power_mw,a.energy_mwh,
            COALESCE(NULLIF(a.tag_number,''),NULLIF(a.equipment_name,''),a.system_asset_number) AS display_name '''
            + equipment_sql + f' ORDER BY {query.sort} {query.direction} NULLS LAST,a.id LIMIT :page_size OFFSET :offset'), params).mappings().all()
        return {'site': dict(site), 'equipment_count': count, 'equipment': [dict(r) for r in rows],
                'page': query.page, 'page_size': query.page_size}
