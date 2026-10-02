"""Asset-owned current location facts for alarm projections; no alarm policy."""
from sqlalchemy import text


def alarm_contexts(engine, at, error):
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
        assets = {str(r['id']): dict(r) for r in c.execute(text('SELECT id,asset_type,serial_number,system_asset_number,product_line FROM formal_assets')).mappings()}
        installations = {}
        for r in c.execute(text('SELECT asset_id,parent_asset_id,site_id FROM asset_installations WHERE valid_from<=:at AND (valid_to IS NULL OR :at<valid_to)'), {'at': at}).mappings():
            key = str(r['asset_id'])
            if key in installations:
                raise error('ambiguous_asset_hierarchy', 409)
            installations[key] = dict(r)
        sites = {str(r['id']): dict(r) for r in c.execute(text('SELECT s.id,s.site_name,s.customer_id,c.customer_name FROM sites s JOIN customers c ON c.id=s.customer_id')).mappings()}
    result = []
    for key, asset in assets.items():
        if asset['asset_type'] != 'TRANSFORMER':
            continue
        path, node, seen = [], key, set()
        while True:
            if node in seen or node not in assets:
                raise error('ambiguous_asset_hierarchy', 409)
            seen.add(node)
            path.append(node)
            link = installations.get(node)
            if not link or not link['parent_asset_id']:
                break
            node = str(link['parent_asset_id'])
        site = sites.get(str(link['site_id'])) if link and link['site_id'] else None
        result.append(dict(id=key, serial_number=asset['serial_number'], system_asset_number=asset['system_asset_number'],
            ancestor_ids=path[1:], product_line=assets[node]['product_line'] or asset['product_line'],
            site_id=str(site['id']) if site else None, site_name=site['site_name'] if site else None,
            customer_id=str(site['customer_id']) if site else None, customer_name=site['customer_name'] if site else None,
            location_kind='SITE' if site else 'REPAIR_CENTER'))
    return tuple(sorted(result, key=lambda a: a['id']))
