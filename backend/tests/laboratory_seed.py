"""Restore placeholder catalog after isolated fixture TRUNCATE users CASCADE.

Method creator FK makes catalog part of that test-only cascade. Never production data.
"""
from sqlalchemy import text


def restore_placeholder_methods(connection):
    labels = {'H2':'H₂','CH4':'CH₄','C2H2':'C₂H₂','C2H4':'C₂H₄','C2H6':'C₂H₆','CO':'CO','CO2':'CO₂',
              'MOISTURE':'微水','BREAKDOWN_VOLTAGE':'击穿电压'}
    for index, (kind, name, fields) in enumerate((
        ('DGA', 'DGA', ('H2','CH4','C2H2','C2H4','C2H6','CO','CO2')),
        ('MOISTURE', '微水', ('MOISTURE',)),
        ('BREAKDOWN_VOLTAGE', '击穿电压', ('BREAKDOWN_VOLTAGE',)),
    ), 1):
        identifier = f'66000000-0000-0000-0000-{index:012d}'
        connection.execute(text('''INSERT INTO test_method_versions
            (id,test_type,display_name,version_label) VALUES (:id,:kind,:name,'MVP-PLACEHOLDER')
            ON CONFLICT DO NOTHING'''), dict(id=identifier, kind=kind, name=f'{name}方法（待配置）'))
        for order, code in enumerate(fields):
            connection.execute(text('''INSERT INTO test_method_fields
                (method_version_id,field_code,display_name,sort_order) VALUES (:id,:code,:label,:sort)
                ON CONFLICT DO NOTHING'''), dict(id=identifier, code=code, label=labels[code], sort=order))
