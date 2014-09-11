#!/usr/bin/env python
"""
Surge unit tests.

"""
from __future__ import division, print_function, unicode_literals, absolute_import
import sys
import os
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
import psycopg2 as db
import psycopg2.extensions as ext
from psycopg2.extras import RealDictCursor

import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "surge"))

from surge import Surge

getcontext().rounding = ROUND_HALF_EVEN
getcontext().prec = 28

BITCOINAVERAGE_API = "https://api.bitcoinaverage.com/"
CRYPTOCOINCHARTS_API = "http://www.cryptocoincharts.info/v2/api/"
BITTREX_API = "https://bittrex.com/api/v1.1/"

class TestSurge(unittest.TestCase):

    def setUp(self):
        self.surge = Surge(verbose=False,
                           update_all_coins=True,
                           coin_list=None,
                           interval=120,
                           max_retry=-1,
                           database_check=False)

    def test_bittrex_orderbook_snapshot(self):
        # self.surge.bittrex_orderbook_snapshot()
        pass

    def test_update_bitcoinaverage(self):
        # self.surge.update_bitcoinaverage()
        pass

    def test_update_cryptocoincharts(self):
        # self.surge.update_cryptocoincharts()
        pass

    def test_update_loop(self):
        pass

    def tearDown(self):
        del self.surge


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSurge)
    unittest.TextTestRunner(verbosity=2).run(suite)
