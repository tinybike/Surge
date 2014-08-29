#!/usr/bin/env python
"""Surge: cryptocurrency data downloader.

Downloads cryptocurrency price data from the public APIs of BitcoinAverage,
CryptoCoinCharts, and CoinMarketCap, and writes to a CSV file (default),
or to a relational database, such as MySQL or PostgreSQL.

Usage:

"""
from __future__ import division, unicode_literals
try:
    import sys
    import cdecimal
    sys.modules["decimal"] = cdecimal
except:
    pass
import os
import getopt
import json
import time
import datetime
import requests
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from contextlib import contextmanager
try:
    import psycopg2 as db
    import psycopg2.extensions as ext
    from psycopg2.extras import RealDictCursor
except:
    import psycopg2cffi as db
    import psycopg2cffi.extensions as ext
    from psycopg2cffi.extras import RealDictCursor

__title__      = "surge"
__version__    = "0.1"
__author__     = "Jack Peterson"
__copyright__  = "Copyright 2014, Dyffy Inc."
__license__    = "MIT"
__maintainer__ = "Jack Peterson"
__email__      = "jack@tinybike.net"

_IS_PYTHON_3 = (platform.version() >= '3')
identity = lambda x : x
if _IS_PYTHON_3:
    u = identity
else:
    import codecs
    def u(string):
        return codecs.unicode_escape_decode(string)[0]

getcontext().prec = 28

BITCOINAVERAGE_API = "https://api.bitcoinaverage.com/"
CRYPTOCOINCHARTS_API = "http://www.cryptocoincharts.info/v2/api/"
BITTREX_API = "https://bittrex.com/api/v1.1/"

# postgres connection
conn = db.connect("host=localhost dbname=analytics user=analytics")
conn.set_isolation_level(ext.ISOLATION_LEVEL_READ_COMMITTED)

class MarketDataTracker(object):
    """
    Download coin price and volume data from third-party APIs
    """
    def __init__(self, update_all_coins=True, max_retry=0,
                 verbose=False, coin_list=None, interval=90):
        self.full = update_all_coins
        self.coin_list = coin_list
        self.max_retry = max_retry
        self.verbose = verbose
        self.interval = interval

    def update_all(self):
        self.update_bitcoinaverage()
        self.update_cryptocoincharts()
        self.bittrex_orderbook_snapshot()

    def bittrex_orderbook_snapshot(self):
        """
        Bittrex API
          public/getorderbook -> JSON
          {
            "result": {
                "buy": 
            },
            "success": true,
          }
        """
        if self.verbose:
            print "Update Bittrex data:"
        try:
            bittrex_url = BITTREX_API + "public/getorderbook?market=%s-%s&type=both&depth=%s"
            ticker1 = "BTC"
            ticker2 = "LTC"
            depth = 50
            if self.verbose:
                print "- Request orderbook from Bittrex (depth: " + str(depth) + ")"
                print bittrex_url % ("ticker1", "ticker2", depth)
            if self.verbose:
                print "Market: %s-%s" % (ticker1, ticker2)
            orderbook = requests.get(bittrex_url % (ticker1, ticker2, depth))
            now = datetime.datetime.now()
            if orderbook.status_code == 200:
                orderbook_dict = orderbook.json()
                if orderbook_dict['success']:
                    if self.verbose:
                        print "- Got orderbook"
                    with cursor() as cur:
                        for buysell in orderbook_dict['result']:
                            if self.verbose:
                                print "- Parse", buysell, "orders"
                            # cur.execute("TRUNCATE orderbook")
                            orders = orderbook_dict['result'][buysell]
                            for order in orders:
                                if self.verbose:
                                    sys.stdout.write('.')
                                    sys.stdout.flush()
                                query = """INSERT INTO orderbook
                                    (ticker1, ticker2,
                                    buy_or_sell, quantity, rate,
                                    total, data_source, updated)
                                    VALUES
                                    (%(ticker1)s, %(ticker2)s, 
                                    %(buy_or_sell)s, %(quantity)s, %(rate)s,
                                    %(total)s, %(data_source)s, %(updated)s)"""
                                parameters = {
                                    'ticker1': ticker1,
                                    'ticker2': ticker2,
                                    'buy_or_sell': buysell[0],
                                    'quantity': order['Quantity'],
                                    'rate': order['Rate'],
                                    'total': order['Quantity'] * order['Rate'],
                                    'data_source': 'bittrex',
                                    'updated': now,
                                }
                                cur.execute(query, parameters)
                            print
        except requests.ConnectionError as err:
            msg = "Error: couldn't connect to Bittrex API"
            timestamp = datetime.datetime.now()
            if self.verbose:
                print msg
                print err
            with open(self.log, 'a') as logfile:
                print >>logfile, str(timestamp) + '\n' + str(err.message) + '\n' + msg
        if self.verbose:
            print "Done."

    def update_bitcoinaverage(self):
        """
        BitcoinAverage (for BTC)
          ticker/USD/last -> last USD/BTC trade (amount in USD)
          ticker/global/USD/ -> JSON
          {
            "24h_avg": 622.37,
            "ask": 621.28,
            "bid": 620.14,
            "last": 621.6,
            "timestamp": "Wed, 23 Jul 2014 03:47:00 -0000",
            "volume_btc": 8968.24,
            "volume_percent": 58.43
          }
        """
        # BitcoinAverage API (vs USD)
        if self.verbose:
            print "Update BitcoinAverage data:"
        coin = 'BTC'
        btc_digits = Decimal(currency_precision(coin))
        bitavg_url = BITCOINAVERAGE_API + "ticker/USD/last"
        volume_bitavg_url = BITCOINAVERAGE_API + "ticker/global/USD/volume_btc"
        if self.verbose:
            print "- Fetching Bitcoin data from BitcoinAverage:"
            print bitavg_url
        self.price = requests.get(bitavg_url).json()
        self.price = Decimal(self.price).quantize(btc_digits, rounding=ROUND_HALF_EVEN)
        volume_btc = Decimal(requests.get(volume_bitavg_url).json()).quantize(
            Decimal(".00001"), rounding=ROUND_HALF_EVEN
        )
        timestamp = datetime.datetime.now()
        select_price_query = (
            "SELECT price FROM coin_data WHERE ticker = %s"
        )
        previous_price = None
        with cursor() as cur:
            cur.execute(select_price_query, (coin,))
            for row in cur:
                previous_price = row[0]
        insert_prices_query = """INSERT INTO coin_data 
            (name, ticker, price, price_btc, 
            data_source, last_update) 
            VALUES 
            (%(name)s, %(ticker)s, %(price)s, %(price_btc)s, 
            %(data_source)s, %(last_update)s)"""
        insert_prices_parameters = {
            'name': currency_codes(coin),
            'ticker': coin,
            'price': self.price,
            'price_btc': Decimal("1.0"),
            'data_source': 'BitcoinAverage',
            'last_update': timestamp,
        }
        with cursor() as cur:
            cur.execute(insert_prices_query, insert_prices_parameters)        
        if self.verbose:
            print "\nDone."

    def update_cryptocoincharts(self):
        """
        CryptoCoinCharts API (for alts)
          /v2/listCoins -> list-of-dicts JSON
          [{
            "id": ticker symbol (e.g. "ltc"),
            "name": coin's name (e.g. "Litecoin"),
            "website": coin's home page (if any),
            "price_btc": price in bitcoins (last traded price @ "best" market),
            "volume_btc": volume traded (in bitcoins) over the past 24 hours
          },...]
        """
        if self.verbose:
            print "Update CryptoCoinCharts data:"
        btc_digits = Decimal(currency_precision('BTC'))
        btc_price = None
        # query = """SELECT price FROM coin_data
        #            WHERE ticker = 'BTC'
        #            ORDER BY last_update DESC"""
        # with cursor() as cur:
        #     cur.execute(query)
        #     if cur.rowcount:
        #         btc_price = cur.fetchone()[0]
        # if btc_price is None:
        # if self.verbose:
        #     print "- No entry for BTC found in coin_data"
        #     print "- Fetching BTC price from BitcoinAverage for comparison"
        btc_price = requests.get(BITCOINAVERAGE_API + "ticker/USD/last").json()
        btc_price = Decimal(btc_price).quantize(btc_digits,
                                                rounding=ROUND_HALF_EVEN)
        # Get altcoin data from CryptoCoinCharts API
        url = CRYPTOCOINCHARTS_API + "listCoins"
        if self.verbose:
            print "- Fetching data from CryptoCoinCharts API"
            print url
        coin_price_list = requests.get(url).json()
        timestamp = datetime.datetime.now()
        if self.verbose:
            num_coins = len(coin_price_list)
            print "-", num_coins, "coins found"
        for i, coin in enumerate(coin_price_list):
            digits = Decimal(currency_precision(coin['id']))
            if self.coin_list is None or (self.coin_list is not None and \
                                          coin['id'].upper() in self.coin_list):
                decimal_price_btc = Decimal(coin['price_btc']).quantize(digits, rounding=ROUND_HALF_EVEN)
                decimal_price_usd = decimal_price_btc * btc_price
                decimal_volume_btc = Decimal(coin['volume_btc']).quantize(btc_digits, rounding=ROUND_HALF_EVEN)
                select_price_query = "SELECT price_btc FROM coin_data WHERE name = %s"
                previous_price = None
                with cursor() as cur:
                    cur.execute(select_price_query, (coin['name'], ))
                    for row in cur:
                        previous_price = row[0]
                # Insert coin data into database
                insert_prices_query = """INSERT INTO coin_data 
                    (name, ticker, price, 
                    price_btc, volume_btc, 
                    data_source, last_update) 
                    VALUES 
                    (%(name)s, %(ticker)s, %(price)s, 
                    %(price_btc)s, %(volume_btc)s, 
                    %(data_source)s, %(last_update)s)"""
                insert_prices_parameters = {
                    'name': coin['name'],
                    'ticker': coin['id'].upper(),
                    'price': decimal_price_usd,
                    'price_btc': decimal_price_btc,
                    'volume_btc': decimal_volume_btc,
                    'data_source': 'CryptoCoinCharts',
                    'last_update': timestamp,
                }
                with cursor() as cur:
                    if self.verbose:
                        count = i + 1
                        progress = round(count / float(num_coins), 3)
                        sys.stdout.write("Loading coin data: " + str(count) + "/" +\
                                         str(num_coins) + " processed [" +\
                                         str(progress * 100) + "%] \r")
                        sys.stdout.flush()
                    cur.execute(insert_prices_query,
                                insert_prices_parameters)

        else:
            if self.verbose:
                print "\nDone."
                return
        if self.verbose:
            sys.stdout.flush()
            print "\nFinished, with errors."

    def update_loop(self):
        restart_counter = 0
        while True:
            if self.verbose:
                print "Starting update loop (interval:", self.interval, "sec)"
            try:
                while True:
                    self.update_cryptocoincharts()
                    self.bittrex_orderbook_snapshot()
                    time.sleep(self.interval - time.time() % self.interval)
            except Exception as exc:
                print "Exception during data update loop:"
                print exc
                time.sleep(5)
                if self.max_retry != -1 and restart_counter > self.max_retry:
                    print "Number of restarts", restart_counter, "exceeds the maximum number of allowed retries", self.max_retry, ". Exiting..."
                    return 2
                else:
                    restart_counter += 1
                    print "Restarting..."


@contextmanager
def cursor(cursor_factory=False):
    """Database cursor generator. Commit on context exit."""
    try:
        if cursor_factory:
            cur = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cur = conn.cursor()
        yield cur
    except (db.Error, Exception) as e:
        cur.close()
        if conn:
            conn.rollback()
        print e.message
        raise
    else:
        conn.commit()
        cur.close()

def currency_precision(currency_code):
    if currency_code.upper() == 'NXT':
        precision = '.01'
    elif currency_code.upper() == 'XRP':
        precision = '.000001'
    else:
        precision = '.00000001'
    return precision

def currency_codes(currency, convert_from="ticker", convert_to="name"):
    """Convert between currencies and their three-letter codes"""
    if convert_from == "name" and convert_to == "name":
        convert_to = "ticker"
    query = "SELECT {convert_to} FROM currencies WHERE {convert_from} = %s".format(
        convert_to=convert_to, convert_from=convert_from
    )
    with cursor() as cur:
        cur.execute(query, (currency,))
        for row in cur:
            return row[0]
    return None

def main(argv=None):
    if argv is None:
        argv = sys.argv
    try:
        short_opts = 'hvsi:m:'
        long_opts = ['help', 'verbose', 'single', 'interval', 'max-retry']
        opts, vals = getopt.getopt(argv[1:], short_opts, long_opts)
    except getopt.GetoptError as e:
        print >>sys.stderr, e.msg
        print >>sys.stderr, "for help use --help"
        return 2
    parameters = {
        'verbose': False,
        'update_all_coins': True,
        'coin_list': None,
        'interval': 60, # 1 minute
        'max_retry': -1, # Set to -1 for unlimited
    }
    run_loop = True
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print __doc__
            return 0
        elif opt in ('-v', '--verbose'):
            parameters['verbose'] = True
        elif opt in ('-s', '--single'):
            run_loop = False
        elif opt in ('-i', '--interval'):
            parameters['interval'] = float(arg)
        elif opt in ('-m', '--max-retry'):
            parameters['max_retry'] = int(arg)
    mdt = MarketDataTracker(**parameters)
    if run_loop:
        mdt.update_loop()
    else:
        # mdt.update_bitcoinaverage()
        mdt.update_cryptocoincharts()
        mdt.bittrex_orderbook_snapshot()
    try:
        if conn:
            conn.close()
    except:
        pass

if __name__ == '__main__':
    sys.exit(main())
