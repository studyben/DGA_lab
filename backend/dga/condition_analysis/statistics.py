"""Descriptive statistics on an already selected comparable numeric series."""
from decimal import Decimal

YEAR_DAYS = Decimal('365.25')


def metric(value=None, reason=None):
    return {'value': value, 'reason': reason}


def elapsed_days(start, end):
    elapsed = end - start
    return (Decimal(elapsed.days) + Decimal(elapsed.seconds) / 86400
            + Decimal(elapsed.microseconds) / 86400000000)


def calculate(points):
    values = [p['value'] for p in points]
    for i, point in enumerate(points):
        point['moving_mean'] = (metric(sum(values[i-2:i+1]) / 3) if i >= 2
                                else metric(reason='need_three_numeric_points'))
        point['delta'] = metric(reason='need_two_numeric_points')
        point['annualized_change'] = metric(reason='need_two_numeric_points')
        if i:
            delta = values[i] - values[i-1]
            days = elapsed_days(points[i-1]['sampled_at'], point['sampled_at'])
            point['delta'] = metric(delta)
            point['annualized_change'] = metric(delta / days * YEAR_DAYS) if days else metric(reason='same_sampling_time')
    slope = metric(reason='need_two_numeric_points')
    if len(points) >= 2:
        xs = [elapsed_days(points[0]['sampled_at'], p['sampled_at']) for p in points]
        x_mean, y_mean = sum(xs) / len(xs), sum(values) / len(values)
        denominator = sum((x - x_mean) ** 2 for x in xs)
        slope = (metric(sum((x-x_mean)*(y-y_mean) for x, y in zip(xs, values)) / denominator * YEAR_DAYS)
                 if denominator else metric(reason='need_distinct_sampling_times'))
    return {
        'minimum': metric(min(values)) if values else metric(reason='no_numeric_points'),
        'maximum': metric(max(values)) if values else metric(reason='no_numeric_points'),
        'mean': metric(sum(values) / len(values)) if values else metric(reason='no_numeric_points'),
        'delta': points[-1]['delta'] if points else metric(reason='need_two_numeric_points'),
        'annualized_change': points[-1]['annualized_change'] if points else metric(reason='need_two_numeric_points'),
        'moving_mean': points[-1]['moving_mean'] if points else metric(reason='need_three_numeric_points'),
        'regression_slope': slope,
    }
