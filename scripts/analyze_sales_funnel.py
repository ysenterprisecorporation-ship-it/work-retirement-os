"""Analyze anonymized aggregate sales without network access or account changes."""
import argparse
import json
import math
from decimal import Decimal
from pathlib import Path


def analyze(data):
    if data.get('internal_tests_excluded') is not True:
        raise ValueError('INTERNAL_TEST_EXCLUSION_REQUIRED')
    counts = {}
    for key in ['visits', 'cart_sessions', 'ordering_sessions', 'completed_orders']:
        value = data.get(key)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('INVALID_COUNT')
        counts[key] = value
    visits = counts['visits']
    for key in ['cart_sessions', 'ordering_sessions']:
        if visits is not None and counts[key] is not None and counts[key] > visits:
            raise ValueError('INVALID_SESSION_COUNTS')
    def rate(n, d):
        return None if n is None or d in [None, 0] else n / d
    money = {}
    for key in ['sales', 'fees', 'other_costs']:
        value = data.get(key)
        if value is not None:
            value = Decimal(str(value))
            if not value.is_finite() or value < 0:
                raise ValueError('INVALID_MONEY')
        money[key] = value
    profit = None
    if all(value is not None for value in money.values()):
        profit = money['sales'] - money['fees'] - money['other_costs']
    upper = None
    if visits and counts['ordering_sessions'] == 0:
        upper = 1 - math.pow(0.05, 1 / visits)
    diagnosis = []
    if visits is None:
        diagnosis.append('VISITS_UNMEASURED_USE_SQUARE_NATIVE_REPORT')
    elif visits == 0:
        diagnosis.append('NO_RECORDED_SITE_VISITS_DISTRIBUTION_FIRST')
    elif counts['cart_sessions'] == 0:
        diagnosis.append('CHECK_AUDIENCE_FIT_AND_PRODUCT_PROOF_NOT_PRICE_ALONE')
    elif counts['cart_sessions'] and counts['ordering_sessions'] == 0:
        diagnosis.append('CHECK_CHECKOUT_TERMS_TOTAL_PRICE_AND_DELIVERY')
    if profit is None:
        diagnosis.append('PROFIT_NOT_VERIFIABLE_COSTS_INCOMPLETE')
    return {
        'period': data.get('period'), 'project': data.get('project'),
        'counts': counts,
        'cart_rate': rate(counts['cart_sessions'], visits),
        'purchase_session_rate': rate(counts['ordering_sessions'], visits),
        'cart_to_purchase_rate': rate(counts['ordering_sessions'], counts['cart_sessions']),
        'zero_purchase_one_sided_95pct_upper_bound': upper,
        'profit': str(profit) if profit is not None else None,
        'diagnosis': diagnosis,
        'assumption': 'Counts are same-period sessions; other_costs includes all adopted profit costs. Independent visits assumed for probability bound.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('aggregate_json', type=Path)
    args = parser.parse_args()
    try:
        result = analyze(json.loads(args.aggregate_json.read_text(encoding='utf-8')))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError):
        parser.exit(2, 'INVALID_OR_INCOMPLETE_AGGREGATE_INPUT\n')
