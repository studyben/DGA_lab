"""Asset-owned effective commands; all mutations serialize graph validation."""
import json
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import text

from dga.shared.auth.public import AuditTrail, require_permission


class AssetAction(StrEnum):
    MOVE = 'ASSET_MOVE'
    STATUS = 'ASSET_STATUS'
    REPLACE = 'TRANSFORMER_REPLACE'
    CORRECT = 'ASSET_HISTORY_CORRECT'


def fail(code, status=409):
    from .public import AssetQueryError
    raise AssetQueryError(code, status)


def asset_row(c, asset_id):
    row = c.execute(text('SELECT * FROM formal_assets WHERE id=:id'), {'id': asset_id}).mappings().first()
    if row is None:
        fail('asset_not_found', 404)
    return dict(row)


def relations(c, asset_id):
    return [dict(r) for r in c.execute(text('SELECT * FROM asset_installations WHERE asset_id=:id ORDER BY valid_from,id'), {'id': asset_id}).mappings()]


def active_relation(c, asset_id, at):
    rows = [r for r in relations(c, asset_id) if r['valid_from'] <= at and (r['valid_to'] is None or at < r['valid_to'])]
    if len(rows) > 1:
        fail('conflicting_installation')
    return rows[0] if rows else None


def status_at(c, asset_id, at):
    row = asset_row(c, asset_id)
    events = c.execute(text('''SELECT effective_at,before_value,after_value FROM asset_lifecycle_events
        WHERE (asset_id=:id OR related_asset_id=:id) AND action<>'ASSET_HISTORY_CORRECT'
        ORDER BY effective_at,occurred_at,id'''), {'id': asset_id}).mappings().all()
    status = events[0]['before_value'][str(asset_id)]['status'] if events else row['lifecycle_status']
    known = False
    for event in events:
        if event['effective_at'] <= at:
            status = event['after_value'][str(asset_id)]['status']
            known = True
    return status, known


def location_at(c, asset_id, at):
    path, visited = [], set()
    current = asset_id
    while current is not None:
        if current in visited or len(visited) >= 100:
            fail('cyclic_installation')
        visited.add(current)
        row = asset_row(c, current)
        path.insert(0, {'id': current, 'serial_number': row['serial_number'], 'system_asset_number': row['system_asset_number']})
        relation = active_relation(c, current, at)
        if not relation:
            return {'kind': 'UNKNOWN', 'path': path, 'site_id': None, 'label': '位置未记录'}
        if relation['repair_center']:
            return {'kind': 'REPAIR_CENTER', 'path': path, 'site_id': None, 'label': '维修中心'}
        if relation['site_id']:
            site = c.execute(text('SELECT site_name FROM sites WHERE id=:id'), {'id': relation['site_id']}).scalar_one()
            return {'kind': 'SITE', 'path': path, 'site_id': relation['site_id'], 'label': site}
        current = relation['parent_asset_id']


def validate_graph(c):
    """Validate every effective topology, not just today's parent chain."""
    rows = [dict(r) for r in c.execute(text('SELECT * FROM asset_installations')).mappings()]
    boundaries = sorted({r[k] for r in rows for k in ('valid_from', 'valid_to') if r[k] is not None})
    for at in boundaries:
        parents = {}
        for row in rows:
            if row['valid_from'] <= at and (row['valid_to'] is None or at < row['valid_to']):
                if row['asset_id'] in parents:
                    fail('conflicting_installation')
                parents[row['asset_id']] = row['parent_asset_id']
        for node in parents:
            visited = set()
            current = node
            while current is not None:
                if current in visited:
                    fail('cyclic_installation')
                visited.add(current)
                current = parents.get(current)


class AssetLifecycle:
    def __init__(self, engine, *, clock=None):
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._audit = AuditTrail(clock=self._clock)

    def catalog(self, actor, *, query='', repair_only=False, page=1):
        require_permission(actor, 'assets.read')
        if not isinstance(query, str) or len(query) > 200 or not isinstance(page, int) or not 1 <= page <= 100000:
            fail('invalid_asset_search', 422)
        with self._engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            where = '''FROM formal_assets a WHERE
                position(lower(:q) in lower(concat_ws(' ',a.serial_number,a.system_asset_number,a.model,a.tag_number)))>0
                AND (:repair=FALSE OR EXISTS (SELECT 1 FROM asset_installations i WHERE i.asset_id=a.id
                    AND i.repair_center AND i.valid_from<=:at AND (i.valid_to IS NULL OR i.valid_to>:at)))'''
            params = {'q': query.strip(), 'repair': repair_only, 'at': self._clock(), 'offset': (page-1)*20}
            total = c.execute(text('SELECT count(*) '+where), params).scalar_one()
            rows = c.execute(text('SELECT a.id,a.system_asset_number,a.serial_number,a.model,a.asset_type,a.lifecycle_status,a.lifecycle_revision '+where+' ORDER BY a.system_asset_number,a.id LIMIT 20 OFFSET :offset'), params).mappings().all()
            sites = c.execute(text('SELECT id,site_name FROM sites ORDER BY site_name,id')).mappings().all()
            return {'assets': [dict(r) for r in rows], 'sites': [dict(s) for s in sites], 'total': total, 'page': page}

    def history(self, actor, asset_id, *, effective_at=None):
        require_permission(actor, 'assets.read')
        at = effective_at or self._clock()
        if at.tzinfo is None:
            fail('effective_at_requires_timezone', 422)
        with self._engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            row = asset_row(c, asset_id)
            events = [dict(e) for e in c.execute(text('''SELECT * FROM asset_lifecycle_events
                WHERE asset_id=:id OR related_asset_id=:id ORDER BY effective_at,occurred_at,id'''), {'id': asset_id}).mappings()]
            status = row['lifecycle_status']
            changes = [e for e in events if e['action'] != AssetAction.CORRECT]
            if changes:
                status = changes[0]['before_value'][str(asset_id)]['status']
                for event in changes:
                    if event['effective_at'] <= at:
                        status = event['after_value'][str(asset_id)]['status']
            return {'asset_id': asset_id, 'revision': row['lifecycle_revision'], 'status': status,
                    'location': location_at(c, asset_id, at), 'installations': relations(c, asset_id),
                    'events': events, 'historical_status_known': bool(changes and at >= changes[0]['effective_at'])}

    def _start(self, c, actor, asset_id, effective_at, reason, expected_revision):
        require_permission(actor, 'assets.write')
        if not isinstance(effective_at, datetime) or effective_at.tzinfo is None or effective_at > self._clock():
            fail('invalid_effective_at', 422)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            fail('reason_required', 422)
        # Serialize all asset graph writes, including cross-root moves and corrections.
        # Reads remain concurrent. A revision token prevents stale UI/retry overwrites.
        c.execute(text('SELECT pg_advisory_xact_lock(110011)'))
        row = asset_row(c, asset_id)
        if row['lifecycle_revision'] != expected_revision:
            fail('stale_asset_revision')
        return row

    def _snapshot(self, c, ids):
        return {str(asset_id): {'status': asset_row(c, asset_id)['lifecycle_status'],
                               'installations': relations(c, asset_id)} for asset_id in ids}

    def _chronology(self, c, asset_id, at):
        last = c.execute(text('''SELECT max(effective_at) FROM asset_lifecycle_events
            WHERE (asset_id=:id OR related_asset_id=:id) AND action<>'ASSET_HISTORY_CORRECT' '''), {'id': asset_id}).scalar()
        if last and at <= last:
            fail('use_history_correction')

    def _record(self, c, actor, action, ids, at, reason, before):
        event_id = uuid4()
        after = self._snapshot(c, ids)
        c.execute(text('''INSERT INTO asset_lifecycle_events
            (id,asset_id,related_asset_id,action,effective_at,occurred_at,actor_id,reason,before_value,after_value)
            VALUES (:id,:asset,:related,:action,:at,:now,:actor,:reason,CAST(:before AS jsonb),CAST(:after AS jsonb))'''),
            {'id': event_id, 'asset': ids[0], 'related': ids[1] if len(ids)>1 else None,
             'action': action.value, 'at': at, 'now': self._clock(), 'actor': actor.user_id,
             'reason': reason.strip(), 'before': json.dumps(before, default=str), 'after': json.dumps(after, default=str)})
        for asset_id in ids:
            c.execute(text('UPDATE formal_assets SET lifecycle_revision=lifecycle_revision+1 WHERE id=:id'), {'id': asset_id})
        self._audit.append(c, actor, action, entity_id=event_id)
        return event_id

    def _move(self, c, asset_id, at, destination, parent_asset_id=None, site_id=None):
        self._chronology(c, asset_id, at)
        row = asset_row(c, asset_id)
        if row['lifecycle_status'] in ('RETIRED', 'MERGED'):
            fail('disabled_asset_cannot_install')
        if destination not in ('PARENT', 'SITE', 'REPAIR_CENTER'):
            fail('invalid_destination', 422)
        if (destination == 'PARENT') != (parent_asset_id is not None) or (destination == 'SITE') != (site_id is not None):
            fail('invalid_destination', 422)
        history = relations(c, asset_id)
        if any(r['valid_from'].astimezone(timezone.utc).date() == at.astimezone(timezone.utc).date() for r in history):
            fail('one_move_per_day')
        if any(r['valid_from'] >= at or (r['valid_to'] and r['valid_to'] > at) for r in history):
            fail('use_history_correction')
        previous = active_relation(c, asset_id, at)
        if destination == 'SITE':
            if row['asset_type'] != 'WHOLE_UNIT':
                fail('only_whole_unit_can_belong_to_site')
            if not c.execute(text('SELECT 1 FROM sites WHERE id=:id'), {'id': site_id}).first():
                fail('site_not_found', 404)
        if destination == 'PARENT':
            parent = asset_row(c, parent_asset_id)
            if parent['lifecycle_status'] in ('RETIRED', 'MERGED'):
                fail('disabled_parent')
            loc = location_at(c, parent_asset_id, at)
            if loc['kind'] != 'SITE':
                fail('parent_not_at_site')
            if any(status_at(c, node['id'], at)[0] in ('RETIRED', 'MERGED') for node in loc['path']):
                fail('disabled_parent')
            if asset_id in [n['id'] for n in loc['path']]:
                fail('cyclic_installation')
        if previous:
            c.execute(text('UPDATE asset_installations SET valid_to=:at WHERE id=:id'), {'id': previous['id'], 'at': at})
        c.execute(text('''INSERT INTO asset_installations(id,asset_id,parent_asset_id,site_id,repair_center,valid_from)
            VALUES (:id,:asset,:parent,:site,:repair,:at)'''), {'id': uuid4(), 'asset': asset_id,
            'parent': parent_asset_id, 'site': site_id, 'repair': destination == 'REPAIR_CENTER', 'at': at})
        status = ('UNDER_REPAIR' if previous else 'SPARE') if destination == 'REPAIR_CENTER' else 'IN_SERVICE'
        c.execute(text('UPDATE formal_assets SET lifecycle_status=:status WHERE id=:id'), {'id': asset_id, 'status': status})

    def move(self, actor, asset_id, *, effective_at, destination, reason, expected_revision, parent_asset_id=None, site_id=None):
        with self._engine.begin() as c:
            self._start(c, actor, asset_id, effective_at, reason, expected_revision)
            before = self._snapshot(c, [asset_id])
            self._move(c, asset_id, effective_at, destination, parent_asset_id, site_id)
            validate_graph(c)
            return self._record(c, actor, AssetAction.MOVE, [asset_id], effective_at, reason, before)

    def change_status(self, actor, asset_id, *, status, effective_at, reason, expected_revision):
        with self._engine.begin() as c:
            row = self._start(c, actor, asset_id, effective_at, reason, expected_revision)
            self._chronology(c, asset_id, effective_at)
            if status not in ('IN_SERVICE', 'UNDER_REPAIR', 'SPARE', 'RETIRED'):
                fail('invalid_lifecycle_status', 422)
            before = self._snapshot(c, [asset_id])
            if row['lifecycle_status'] == 'RETIRED' and status == 'SPARE' and active_relation(c, asset_id, effective_at) is None:
                if any(r['valid_from'] >= effective_at or (r['valid_to'] and r['valid_to'] > effective_at) for r in relations(c, asset_id)):
                    fail('use_history_correction')
                c.execute(text('''INSERT INTO asset_installations(id,asset_id,repair_center,valid_from)
                    VALUES (:id,:asset,TRUE,:at)'''), {'id': uuid4(), 'asset': asset_id, 'at': effective_at})
            location = location_at(c, asset_id, effective_at)
            if status in ('UNDER_REPAIR', 'SPARE') and (location['kind'] != 'REPAIR_CENTER' or len(location['path']) != 1):
                fail('status_requires_repair_center')
            if status == 'IN_SERVICE' and location['kind'] != 'SITE':
                fail('in_service_requires_site')
            if row['lifecycle_status'] == status:
                fail('status_unchanged')
            c.execute(text('UPDATE formal_assets SET lifecycle_status=:status WHERE id=:id'), {'id': asset_id, 'status': status})
            return self._record(c, actor, AssetAction.STATUS, [asset_id], effective_at, reason, before)

    def replace_transformer(self, actor, asset_id, *, replacement_id, effective_at, reason, expected_revision, replacement_revision):
        with self._engine.begin() as c:
            old = self._start(c, actor, asset_id, effective_at, reason, expected_revision)
            new = self._start(c, actor, replacement_id, effective_at, reason, replacement_revision)
            if asset_id == replacement_id or old['asset_type'] != 'TRANSFORMER' or new['asset_type'] != 'TRANSFORMER':
                fail('replacement_requires_distinct_transformers', 422)
            installation = active_relation(c, asset_id, effective_at)
            replacement_location = location_at(c, replacement_id, effective_at)
            if not installation or not installation['parent_asset_id']:
                fail('old_transformer_not_installed')
            if new['lifecycle_status'] != 'SPARE' or replacement_location['kind'] != 'REPAIR_CENTER' or len(replacement_location['path']) != 1:
                fail('replacement_not_spare')
            before = self._snapshot(c, [asset_id, replacement_id])
            self._move(c, asset_id, effective_at, 'REPAIR_CENTER')
            self._move(c, replacement_id, effective_at, 'PARENT', installation['parent_asset_id'])
            validate_graph(c)
            return self._record(c, actor, AssetAction.REPLACE, [asset_id, replacement_id], effective_at, reason, before)

    def correct_installation(self, actor, asset_id, *, installation_id, valid_from, valid_to,
                             parent_asset_id, site_id, repair_center, reason, expected_revision):
        require_permission(actor, 'assets.history.correct')
        with self._engine.begin() as c:
            row = self._start(c, actor, asset_id, valid_from, reason, expected_revision)
            if valid_to is not None and (valid_to.tzinfo is None or valid_to <= valid_from or valid_to > self._clock()):
                fail('invalid_effective_interval', 422)
            if sum((parent_asset_id is not None, site_id is not None, repair_center)) != 1:
                fail('invalid_destination', 422)
            if parent_asset_id == asset_id:
                fail('cyclic_installation')
            if parent_asset_id is not None:
                asset_row(c, parent_asset_id)
            if site_id is not None:
                if row['asset_type'] != 'WHOLE_UNIT':
                    fail('only_whole_unit_can_belong_to_site')
                if not c.execute(text('SELECT 1 FROM sites WHERE id=:id'), {'id': site_id}).first():
                    fail('site_not_found', 404)
            before = self._snapshot(c, [asset_id])
            original = next((r for r in before[str(asset_id)]['installations'] if r['id'] == installation_id), None)
            if original is None:
                fail('installation_not_found', 404)
            # Reject conflicts before hitting the existing unique open-interval index.
            for other in before[str(asset_id)]['installations']:
                if other['id'] != installation_id and (valid_to is None or other['valid_from'] < valid_to) and (other['valid_to'] is None or valid_from < other['valid_to']):
                    fail('conflicting_installation')
                if other['id'] != installation_id and (
                    (other['valid_to'] == original['valid_from'] and valid_from != original['valid_from']) or
                    (original['valid_to'] == other['valid_from'] and valid_to != original['valid_to'])
                ):
                    fail('history_gap')
            if original['valid_to'] is None and valid_to is not None:
                fail('history_gap')
            c.execute(text('''UPDATE asset_installations SET valid_from=:start,valid_to=:end,
                parent_asset_id=:parent,site_id=:site,repair_center=:repair WHERE id=:id'''),
                {'id': installation_id, 'start': valid_from, 'end': valid_to,
                 'parent': parent_asset_id, 'site': site_id, 'repair': repair_center})
            validate_graph(c)
            # Corrections cannot manufacture an installation during a known spare,
            # repair or disabled period. No guessed timestamps for legacy states.
            now = self._clock()
            boundaries = {valid_from, now}
            # Ancestors can change state/location within the corrected interval.
            boundaries.update(c.execute(text('SELECT effective_at FROM asset_lifecycle_events')).scalars())
            boundaries.update(c.execute(text('SELECT valid_from FROM asset_installations UNION SELECT valid_to FROM asset_installations WHERE valid_to IS NOT NULL')).scalars())
            target_changed = any(original[key] != value for key, value in
                                 [('parent_asset_id', parent_asset_id), ('site_id', site_id), ('repair_center', repair_center)])
            for instant in boundaries:
                if instant < valid_from or (valid_to is not None and instant >= valid_to):
                    continue
                status, known = status_at(c, asset_id, instant)
                newly_covered = target_changed or instant < original['valid_from'] or (original['valid_to'] is not None and instant >= original['valid_to'])
                if known or instant == now:
                    if status in ('RETIRED', 'MERGED') and newly_covered:
                        fail('disabled_asset_cannot_install')
                    if (repair_center and status == 'IN_SERVICE') or (not repair_center and status in ('UNDER_REPAIR', 'SPARE')):
                        fail('status_location_conflict')
                if parent_asset_id is not None and newly_covered:
                    parent_location = location_at(c, parent_asset_id, instant)
                    if parent_location['kind'] != 'SITE':
                        fail('parent_not_at_site')
                    for node in parent_location['path']:
                        parent_status, parent_known = status_at(c, node['id'], instant)
                        if (parent_known or instant == now) and parent_status in ('RETIRED', 'MERGED'):
                            fail('disabled_parent')
            return self._record(c, actor, AssetAction.CORRECT, [asset_id], self._clock(), reason, before)
