"""Proposed approved policy for pre-migration operator impact reports; no writes."""
READ = frozenset({'assets.read', 'laboratory.read', 'analysis.read'})
POLICY = {
    'system_admin': READ | {'assets.write', 'assets.site.edit', 'assets.history.correct', 'assets.import',
        'laboratory.write', 'laboratory.finalize', 'laboratory.configure', 'analysis.write',
        'analysis.acknowledge', 'identity.manage', 'identity.ordinary.manage', 'identity.am.manage', 'audit.read'},
    'lab_admin': READ | {'assets.write', 'assets.site.edit', 'assets.history.correct',
        'laboratory.write', 'laboratory.finalize', 'laboratory.configure', 'analysis.write',
        'analysis.acknowledge', 'identity.ordinary.manage', 'audit.read'},
    'analyst': READ | {'laboratory.write', 'laboratory.finalize', 'analysis.acknowledge'},
    'field_engineer': READ | {'analysis.acknowledge'},
    'asset_manager': READ | {'assets.site.edit'},
    'management': READ | {'assets.site.edit', 'identity.am.manage'},
}
