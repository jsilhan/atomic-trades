from atomic_trades.commands import CurrencyConversion
from atomic_trades.functions import evaluate_pre_conditions
from tests.base import BaseTestCase


class CurrencyConversionTestCase(BaseTestCase):

    def setUp(self) -> None:
        self.exchange = self.create_mocked_exchange(name='FTX')

    async def test_currency_conversion_forward_symbol(self) -> None:
        currency_convertor = CurrencyConversion(self.exchange, 'USD', 'LTC')
        command = self.create_command(self.exchange, pre_conditions={currency_convertor})
        assert not currency_convertor.is_symbol_reversed
        assert currency_convertor.converting_symbol == 'LTC/USD'
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        assert currency_convertor.convert_amount(175) == 1
        assert failed_conditions == set()
        assert successful_conditions == set()

    async def test_currency_conversion_reversed_symbol(self) -> None:
        currency_convertor = CurrencyConversion(self.exchange, 'LTC', 'USD')
        command = self.create_command(self.exchange, pre_conditions={currency_convertor})
        assert currency_convertor.is_symbol_reversed
        assert currency_convertor.converting_symbol == 'LTC/USD'
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        assert currency_convertor.convert_amount(1) == 176
        assert failed_conditions == set()
        assert successful_conditions == set()

    async def test_currency_conversion_same_currency(self) -> None:
        currency_convertor = CurrencyConversion(self.exchange, 'USD', 'USD')
        command = self.create_command(self.exchange, pre_conditions={currency_convertor})
        assert not currency_convertor.is_symbol_reversed
        assert currency_convertor.converting_symbol is None
        await evaluate_pre_conditions(command)
        assert currency_convertor.convert_amount(2000) == 2000
