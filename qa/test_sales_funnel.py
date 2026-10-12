import unittest
from scripts.analyze_sales_funnel import analyze


class FunnelTests(unittest.TestCase):
    def test_unknown_is_not_zero(self):
        result = analyze({'internal_tests_excluded': True})
        self.assertIsNone(result['cart_rate'])
        self.assertIsNone(result['profit'])

    def test_internal_test_is_not_customer_sale(self):
        with self.assertRaises(ValueError):
            analyze({'internal_tests_excluded': False, 'sales': 2980})

    def test_checkout_and_complete_costs(self):
        result = analyze({'internal_tests_excluded': True, 'visits': 100,
                          'cart_sessions': 10, 'ordering_sessions': 2,
                          'completed_orders': 2, 'sales': 20000,
                          'fees': 1000, 'other_costs': 3000})
        self.assertEqual(result['cart_to_purchase_rate'], 0.2)
        self.assertEqual(result['profit'], '16000')

    def test_zero_orders_bound_and_invalid_counts(self):
        result = analyze({'internal_tests_excluded': True, 'visits': 150,
                          'ordering_sessions': 0})
        self.assertLess(result['zero_purchase_one_sided_95pct_upper_bound'], 0.02)
        with self.assertRaises(ValueError):
            analyze({'internal_tests_excluded': True, 'visits': 1, 'cart_sessions': 2})


if __name__ == '__main__':
    unittest.main()
