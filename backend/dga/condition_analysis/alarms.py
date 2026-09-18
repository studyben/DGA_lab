"""Persistent alarm lifecycle behind the analysis public interface."""
from datetime import datetime, timezone
from enum import StrEnum
from dataclasses import asdict
from hashlib import sha256
import json
from uuid import uuid4
from sqlalchemy import text
from dga.assets.public import AlarmAssetReader
from dga.laboratory.public import HealthResultReader
from dga.shared.auth.public import require_permission, AuditTrail
from .rules import encode, HealthError, validate_revision
from .alarm_inputs import stable_observation, assessments, worst


class _Action(StrEnum):
    ACKNOWLEDGED = 'ALARM_ACKNOWLEDGED'


class AlarmCenter:
    def __init__(self, engine, assets: AlarmAssetReader, laboratory: HealthResultReader, *, clock=None):
        self.engine, self.assets, self.laboratory = engine, assets, laboratory
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _event(self, c, alarm, action, now, actor_id=None):
        c.execute(text('INSERT INTO alarm_events(id,episode_id,revision,occurred_at,action,actor_id,data) VALUES(:id,:episode,:revision,:at,:action,:actor,CAST(:data AS jsonb))'),
            dict(id=uuid4(),episode=alarm['id'],revision=alarm['revision'],at=now,action=action,actor=actor_id,data=encode(alarm)))

    def _rows(self, c):
        return [dict(r['data']) for r in c.execute(text('SELECT data FROM alarm_episodes ORDER BY opened_at,id')).mappings()]

    def _save(self, c, alarm, action, now, actor_id=None):
        alarm['revision'] += 1
        c.execute(text('UPDATE alarm_episodes SET state=:state,revision=:revision,superseded_by=:superseded_by,data=CAST(:data AS jsonb) WHERE id=:id'),alarm|{'data':encode(alarm)})
        self._event(c,alarm,action,now,actor_id)

    def acknowledge(self, actor, identifier, expected_revision, note):
        require_permission(actor, 'analysis.acknowledge')
        validate_revision(expected_revision)
        if not isinstance(note,str) or not 1<=len(note.strip())<=1000:
            raise HealthError('alarm_note_required')
        self._refresh(actor)
        with self.engine.begin() as c:
            c.execute(text('SELECT version FROM alarm_generation WHERE id=1 FOR UPDATE'))
            alarm = next((a for a in self._rows(c) if a['id']==str(identifier)),None)
            if alarm is None:
                raise HealthError('alarm_not_found',404)
            if alarm['state']=='RESOLVED' or alarm['superseded_by']:
                raise HealthError('alarm_not_open',409)
            if alarm['acknowledgement']:
                return alarm
            if alarm['revision']!=expected_revision:
                raise HealthError('alarm_revision_conflict',409)
            now = self.clock()
            alarm['state']='ACKNOWLEDGED'
            alarm['acknowledgement']=dict(actor_id=str(actor.user_id),actor_name=actor.display_name,at=now.isoformat(),note=note.strip())
            self._save(c,alarm,'ACKNOWLEDGED',now,actor.user_id)
            AuditTrail(clock=self.clock).append(c,actor,_Action.ACKNOWLEDGED,entity_id=identifier)
            c.execute(text('UPDATE alarm_generation SET version=version+1 WHERE id=1'))
            return alarm

    def _refresh(self, actor):
        require_permission(actor, 'analysis.read')
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise HealthError('timezone_required')
        for _ in range(3):
            with self.engine.connect() as c:
                generation = c.execute(text('SELECT version FROM alarm_generation WHERE id=1')).scalar_one()
            contexts, points, policies = stable_observation(self.engine,self.assets,self.laboratory,actor,now)
            observed = assessments(points,policies)
            fingerprint = sha256(encode((contexts,[asdict(p) for p in points],policies)).encode()).hexdigest()
            with self.engine.begin() as c:
                current = c.execute(text('SELECT version,fingerprint FROM alarm_generation WHERE id=1 FOR UPDATE')).mappings().one()
                if current['version'] != generation:
                    continue
                rows = self._rows(c)
                for key, sources in observed.items():
                    source = worst(sources)
                    if source['status'] not in ('ATTENTION','WARNING','CRITICAL'):
                        continue
                    existing = next((a for a in rows if (a['asset_id'],a['test_type'],a['analyte'])==key and a['state']!='RESOLVED' and not a['superseded_by']),None)
                    if existing:
                        continue
                    alarm = dict(id=str(uuid4()),asset_id=key[0],test_type=key[1],analyte=key[2],state='UNACKNOWLEDGED',
                        revision=0,opened_at=now.isoformat(),superseded_by=None,trigger=source,latest_abnormal=sources,
                        severity=source['status'],acknowledgement=None,recovery=None)
                    c.execute(text('INSERT INTO alarm_episodes(id,asset_id,test_type,analyte,state,revision,opened_at,data) VALUES(:id,:asset_id,:test_type,:analyte,:state,:revision,:opened_at,CAST(:data AS jsonb))'),alarm|{'data':encode(alarm)})
                    self._event(c,alarm,'OPENED',now)
                    rows.append(alarm)
                if fingerprint != current['fingerprint']:
                    c.execute(text('UPDATE alarm_generation SET version=version+1,fingerprint=:fingerprint WHERE id=1'),{'fingerprint':fingerprint})
                return rows, {a['id']:a for a in contexts}, now
        raise HealthError('alarm_inputs_changed',409)

    def query(self, actor):
        rows, contexts, now = self._refresh(actor)
        rows = [a|{'current_asset':contexts.get(a['asset_id'])} for a in rows if not a['superseded_by']]
        return dict(items=rows,total=len(rows),unresolved_count=sum(a['state']!='RESOLVED' for a in rows),checked_at=now.isoformat())

    def detail(self, actor, identifier):
        rows, contexts, now = self._refresh(actor)
        alarm = next((a for a in rows if a['id']==str(identifier)),None)
        if alarm is None:
            raise HealthError('alarm_not_found',404)
        with self.engine.connect() as c:
            events = [dict(r) for r in c.execute(text('SELECT action,occurred_at,actor_id,data FROM alarm_events WHERE episode_id=:id AND revision<=:revision ORDER BY revision'),{'id':identifier,'revision':alarm['revision']}).mappings()]
        return alarm|dict(events=events,current_asset=contexts.get(alarm['asset_id']),checked_at=now.isoformat())
