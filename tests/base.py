import aiounittest
from unittest import mock

from atomic_trades.commands import BaseCommand
from ccxt.base.errors import OrderNotFound


BALANCE_DATA = {
    'total': {
        'USD': 100,
        'ETH': 0.4,
        'LTC': 175,
        'BTC': 2,
    },
    'free': {
        'USD': 68,
        'ETH': 0.00034843,
        'LTC': 75.8495265,
        'BTC': 1,
    }
}


async def mocked_fetch_positions_response(*args, **kwargs):
    return [
        {'future': 'ETH-0625',
         'size': '4.242',
         'side': 'sell',
         'netSize': '-4.242',
         'longOrderSize': '0.0',
         'shortOrderSize': '0.0',
         'cost': '-9993.7278',
         'entryPrice': '2355.9',
         'unrealizedPnl': '0.0',
         'realizedPnl': '-7247.685',
         'initialMarginRequirement': '0.33333333',
         'maintenanceMarginRequirement': '0.03',
         'openSize': '4.242',
         'collateralUsed': '3331.242566687574',
         'estimatedLiquidationPrice': '231325.66429421087'},
        {'future': 'BTC-1231',
         'size': '0.0',
         'side': 'buy',
         'netSize': '0.0',
         'longOrderSize': '0.0',
         'shortOrderSize': '0.0',
         'cost': '0.0',
         'entryPrice': None,
         'unrealizedPnl': '0.0',
         'realizedPnl': '-650.5944',
         'initialMarginRequirement': '0.33333333',
         'maintenanceMarginRequirement': '0.03',
         'openSize': '0.0',
         'collateralUsed': '0.0',
         'estimatedLiquidationPrice': '0.0'}
    ]


async def mocked_cancel_order_filled_response(*args, **kwargs):
    raise OrderNotFound


async def mocked_cancel_order_successful_response(*args, **kwargs):
    return 'Order set for cancellation'


async def mocked_fetch_order_partially_filled_response(*args, **kwargs):
    return {
        'id': 33,
        'filled': 0.0001
    }


async def mocked_fetch_order_open_response(*args, **kwargs):
    return {
        'id': 33,
        'filled': 0
    }


async def mocked_fetch_order_status_open_response(*args, **kwargs):
    return 'open'


async def mocked_fetch_order_status_filled_response(*args, **kwargs):
    return 'filled'


async def mocked_create_order_response(*args, **kwargs):
    return {
        'id': 33
    }


async def mocked_fetch_balance_response(*args, **kwargs):
    return BALANCE_DATA


async def mocked_fetch_tickers_response(*args, **kwargs):
    return {
        'ETH/USD': {
            'ask': 1528,
            'bid': 1526
        },
        'LTC/USD': {
            'ask': 176,
            'bid': 175
        },
        'BTC/USD': {
            'ask': 47327,
            'bid': 47324
        },
        'ETH/BTC': {
            'ask': 0.0358,
            'bid': 0.0357
        },
        'SOL/USD': {
            'ask': 30.16,
            'bid': 30.05
        },
        'ETH-0625': {
            'ask': 1628,
            'bid': 1626
        }
    }


markets_data = {
    'BTC/USD': {
        'maker': 0.0002,
        'taker': 0.0007000000000000001,
    },
    'ETH/USD': {
        'maker': 0.0002,
        'taker': 0.0007000000000000001,
    },
    'LTC/USD': {
        'maker': 0.0002,
        'taker': 0.0007000000000000001,
    },
    'ETH/BTC': {
        'maker': 0.0002,
        'taker': 0.0007000000000000001,
    },
    'LTC/BTC': {
        'maker': 0.0002,
        'taker': 0.0007000000000000001,
    },
    'SOL/USD': {
        'maker': 0.0002,
        'taker': 0.0007000000000000001,
    },
}


class BaseTestCase(aiounittest.AsyncTestCase):

    def create_mocked_exchange(self, name):
        exchange = mock.MagicMock()
        exchange.name = name
        exchange.fetch_balance.side_effect = mocked_fetch_balance_response
        exchange.fetch_tickers.side_effect = mocked_fetch_tickers_response
        exchange.fetch_positions.side_effect = mocked_fetch_positions_response
        exchange.fetch_order.side_effect = mocked_fetch_order_open_response
        exchange.create_order.side_effect = mocked_create_order_response
        exchange.cancel_order.side_effect = mocked_cancel_order_successful_response
        exchange.fetch_order_status.side_effect = mocked_fetch_order_status_open_response
        exchange.markets = markets_data
        return exchange

    def create_command(self, exchange, pre_conditions=None):
        class TestCommand(BaseCommand):

            def __init__(self, exchange):
                super().__init__(exchange)

            def pre_conditions(self):
                return set(pre_conditions or {})

        return TestCommand(exchange)
