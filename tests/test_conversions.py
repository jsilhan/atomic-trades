from nose.tools import assert_equal, assert_false, assert_true

from tests.base import BaseTestCase
from atomic_trades.commands import CurrencyConversion
from atomic_trades.functions import evaluate_pre_conditions


class CurrencyConversionTestCase(BaseTestCase):

    def setUp(self) -> None:
        self.exchange = self.create_mocked_exchange(name='FTX')

    async def test_currency_conversion_forward_symbol(self) -> None:
        currency_convertor = CurrencyConversion(self.exchange, 'USD', 'LTC')
        command = self.create_command(self.exchange, pre_conditions={currency_convertor})
        assert_false(currency_convertor.is_symbol_reversed)
        assert_equal(currency_convertor.converting_symbol, 'LTC/USD')
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        assert_equal(1, currency_convertor.convert_amount(175))
        assert_equal(failed_conditions, set())
        assert_equal(successful_conditions, set())

    async def test_currency_conversion_reversed_symbol(self) -> None:
        currency_convertor = CurrencyConversion(self.exchange, 'LTC', 'USD')
        command = self.create_command(self.exchange, pre_conditions={currency_convertor})
        assert_true(currency_convertor.is_symbol_reversed)
        assert_equal(currency_convertor.converting_symbol, 'LTC/USD')
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        assert_equal(176, currency_convertor.convert_amount(1))
        assert_equal(failed_conditions, set())
        assert_equal(successful_conditions, set())

    async def test_currency_conversion_same_currency(self) -> None:
        currency_convertor = CurrencyConversion(self.exchange, 'USD', 'USD')
        command = self.create_command(self.exchange, pre_conditions={currency_convertor})
        assert_false(currency_convertor.is_symbol_reversed)
        assert_equal(currency_convertor.converting_symbol, None)
        await evaluate_pre_conditions(command)
        amount = 2000
        assert_equal(amount, currency_convertor.convert_amount(amount))
