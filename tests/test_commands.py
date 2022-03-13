from mock import call
from nose.tools import assert_equal, assert_raises

from atomic_trades.commands import (BalanceCondition, BaseCommand, BuyPosition,
                                    ExchangeAllCurrency, ExchangeCurrency,
                                    SellPosition)
from atomic_trades.conditions import PositionCondition
from atomic_trades.exceptions import (CommandExecutionError,
                                      MarketDoesNotExistsError,
                                      PostConditionError, PreConditionError)
from atomic_trades.functions import evaluate_pre_conditions, execute_commands
from tests.base import (BALANCE_DATA, BaseTestCase,
                        mocked_cancel_order_filled_response,
                        mocked_fetch_order_partially_filled_response,
                        mocked_fetch_order_status_filled_response)


class CommandTestCase(BaseTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.exchange = self.create_mocked_exchange('FTX')

    async def test_exchange_currency_command_evaluation_amount_in_buying_currency(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=4)
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        self.exchange.fetch_balance.assert_called_once()
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        assert_equal(successful_conditions, {BalanceCondition(self.exchange, 'BTC', '>=', 4, in_currency='ETH')})
        assert_equal(failed_conditions, set())

    async def test_exchange_currency_command_execution_amount_in_buying_currency(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=4)
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {BalanceCondition(self.exchange, 'ETH', '>', BALANCE_DATA['free']['ETH']),
                      BalanceCondition(self.exchange, 'BTC', '<', 1)})
        assert_equal(self.exchange.fetch_balance.call_count, 2)
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        self.exchange.create_order.assert_called_once_with(symbol='ETH/BTC', type='market', side='buy',
                                                           amount=4, params={})

    async def test_exchange_currency_command_evaluation_insufficient_amount(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=40)
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        self.exchange.fetch_balance.assert_called_once()
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        assert_equal(failed_conditions, {BalanceCondition(self.exchange, 'BTC', 'gte', 40, in_currency='ETH')})
        assert_equal(successful_conditions, set())

    async def test_raises_market_does_not_exists_error(self) -> None:
        with assert_raises(MarketDoesNotExistsError):
            ExchangeCurrency(self.exchange, 'BTC', 'SPX', amount=40)

    async def test_exchange_currency_command_evaluation_amount_in_buying_currency_eth(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=4, in_currency='ETH')
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        self.exchange.fetch_balance.assert_called_once()
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        assert_equal(successful_conditions, {BalanceCondition(self.exchange, 'BTC', 'gte', 4, in_currency='ETH')})
        assert_equal(failed_conditions, set())

    async def test_exchange_currency_command_execution_amount_in_buying_currency_eth(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=4, in_currency='ETH')
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {BalanceCondition(self.exchange, 'ETH', '>', BALANCE_DATA['free']['ETH']),
                      BalanceCondition(self.exchange, 'BTC', '<', 1)})
        assert_equal(self.exchange.fetch_balance.call_count, 2)
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        self.exchange.create_order.assert_called_once_with(symbol='ETH/BTC', type='market', side='buy', amount=4,
                                                           params={})

    async def test_exchange_currency_command_reversed_symbol_amount_in_usd_currency(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'USD', amount=5, in_currency='USD')
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {BalanceCondition(self.exchange, 'USD', '>', BALANCE_DATA['free']['USD']),
                      BalanceCondition(self.exchange, 'BTC', '<', 1)})
        assert_equal(self.exchange.fetch_balance.call_count, 2)
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'BTC/USD'})
        self.exchange.create_order.assert_called_once_with(symbol='BTC/USD', type='market', side='sell',
                                                           amount=0.00010565463612543319, params={})

    async def test_exchange_currency_command_evaluation_amount_in_usd_currency(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=6800, in_currency='USD')
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        self.exchange.fetch_balance.assert_called_once()
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/USD', 'BTC/USD'})
        assert_equal(successful_conditions, {BalanceCondition(self.exchange, 'BTC', 'gte', 6800, in_currency='USD')})
        assert_equal(failed_conditions, set())

    async def test_exchange_currency_command_execution_amount_in_usd_currency(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=4, in_currency='USD')
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {BalanceCondition(self.exchange, 'ETH', '>', BALANCE_DATA['free']['ETH']),
                      BalanceCondition(self.exchange, 'BTC', '<', 1)})
        assert_equal(self.exchange.fetch_balance.call_count, 2)
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/USD', 'BTC/USD'})
        self.exchange.create_order.assert_called_once_with(symbol='ETH/BTC', type='market', side='buy',
                                                           amount=0.002621231979030144, params={})

    async def test_exchange_currency_command_evaluation_amount_in_selling_currency(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=1, in_currency='BTC')
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        self.exchange.fetch_balance.assert_called_once()
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        assert_equal(successful_conditions, {BalanceCondition(self.exchange, 'BTC', 'gte', 1)})
        assert_equal(failed_conditions, set())

    async def test_exchange_currency_command_execution_amount_in_selling_currency(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=1, in_currency='BTC')
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {BalanceCondition(self.exchange, 'ETH', '>', BALANCE_DATA['free']['ETH']),
                      BalanceCondition(self.exchange, 'BTC', '<', 1)})
        assert_equal(self.exchange.fetch_balance.call_count, 2)
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        self.exchange.create_order.assert_called_once_with(symbol='ETH/BTC', type='market', side='buy',
                                                           amount=28.011204481792713, params={})

    async def test_exchange_currency_command_evaluation_amount_in_selling_currency_insufficient_amount(self) -> None:
        command = ExchangeCurrency(self.exchange, 'BTC', 'ETH', amount=10, in_currency='BTC')
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        self.exchange.fetch_balance.assert_called_once()
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        assert_equal(successful_conditions, set())
        assert_equal(failed_conditions, {BalanceCondition(self.exchange, 'BTC', 'gte', 10)})

    async def test_exchange_all_currency_command_execution_success(self) -> None:
        command = ExchangeAllCurrency(self.exchange, 'BTC', 'ETH')
        with assert_raises(PostConditionError):
            # balances do not change in mocked call so post condition error fails
            await execute_commands(command)
        assert_equal(self.exchange.fetch_balance.call_count, 2)
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        self.exchange.create_order.assert_called_once_with(symbol='ETH/BTC', type='market', side='buy',
                                                           amount=28.011204481792713, params={})

    async def test_exchange_all_currency_command_execution_success_reversed_symbol(self) -> None:
        command = ExchangeAllCurrency(self.exchange, 'ETH', 'BTC')
        with assert_raises(PostConditionError) as cm:
            # balances do not change in mocked call so post condition error fails
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {BalanceCondition(self.exchange, 'ETH', '<', BALANCE_DATA['free']['ETH']),
                      BalanceCondition(self.exchange, 'BTC', '>', 1)})
        assert_equal(self.exchange.fetch_balance.call_count, 2)
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'ETH/BTC'})
        self.exchange.create_order.assert_called_once_with(symbol='ETH/BTC', type='market', side='sell',
                                                           amount=BALANCE_DATA['free']['ETH'], params={})

    async def test_exchange_all_currency_command_execution_unknown_symbol_raises_pre_condition_error(self) -> None:
        command = ExchangeAllCurrency(self.exchange, 'SOL', 'USD')
        with assert_raises(PreConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions, {command.selling_currency_balance_condition})

    async def test_execute_commands_raises_command_execution_error(self) -> None:
        error_command = BaseCommand(self.exchange)  # when execute method is not defined raises Error
        successful_command = ExchangeAllCurrency(self.exchange, 'ETH', 'BTC')
        with assert_raises(CommandExecutionError) as cm:
            await execute_commands(successful_command, error_command)
        assert_equal(len(cm.exception.failed_commands_dict), 1)
        assert_equal(cm.exception.failed_commands_dict[error_command].__class__, NotImplementedError)
        with assert_raises(CommandExecutionError) as cm:
            await execute_commands(error_command, successful_command)
        assert_equal(len(cm.exception.failed_commands_dict), 1)
        assert_equal(cm.exception.failed_commands_dict[error_command].__class__, NotImplementedError)

    async def test_negative_amount_passed_into_command(self) -> None:
        with assert_raises(AssertionError):
            ExchangeCurrency(self.exchange, 'ETH', 'BTC', -7)

    async def test_execute_till_command_creates_market_taker_after_timeout(self) -> None:
        command = ExchangeAllCurrency(self.exchange, 'ETH', 'BTC', execute_till=0.7)
        with assert_raises(PostConditionError):
            await execute_commands(command)
        calls = [call(symbol='ETH/BTC', type='limit', side='sell', amount=0.00034843, price=0.035750000000000004),
                 call(symbol='ETH/BTC', type='market', side='sell', amount=0.00034843, params={})]
        self.exchange.create_order.assert_has_calls(calls)
        assert_equal(self.exchange.fetch_order_status.call_count, 2)
        self.exchange.cancel_order.assert_called_once_with(id=33, symbol='ETH/BTC')

    async def test_execute_till_command_creates_market_taker_after_timeout_when_partially_filled(self) -> None:
        self.exchange.fetch_order.side_effect = mocked_fetch_order_partially_filled_response
        command = ExchangeAllCurrency(self.exchange, 'ETH', 'BTC', execute_till=0.7)
        with assert_raises(PostConditionError):
            await execute_commands(command)
        calls = [call(symbol='ETH/BTC', type='limit', side='sell', amount=0.00034843, price=0.035750000000000004),
                 call(symbol='ETH/BTC', type='market', side='sell', amount=0.00024843, params={})]
        self.exchange.create_order.assert_has_calls(calls)
        assert_equal(self.exchange.fetch_order_status.call_count, 2)
        self.exchange.cancel_order.assert_called_once_with(id=33, symbol='ETH/BTC')

    async def test_execute_till_command_not_creates_market_taker_when_filled_during_timeout_period(self) -> None:
        self.exchange.fetch_order_status.side_effect = mocked_fetch_order_status_filled_response
        command = ExchangeAllCurrency(self.exchange, 'ETH', 'BTC', execute_till=0.7)
        with assert_raises(PostConditionError):
            await execute_commands(command)
        self.exchange.create_order.assert_called_once_with(
            symbol='ETH/BTC', type='limit', side='sell', amount=0.00034843, price=0.035750000000000004
        )
        assert_equal(self.exchange.fetch_order_status.call_count, 1)
        self.exchange.cancel_order.assert_not_called()

    async def test_execute_till_command_not_creates_market_taker_when_filled_during_cancellation(self) -> None:
        self.exchange.cancel_order.side_effect = mocked_cancel_order_filled_response
        command = ExchangeAllCurrency(self.exchange, 'ETH', 'BTC', execute_till=0.7)
        with assert_raises(PostConditionError):
            await execute_commands(command)
        self.exchange.create_order.assert_called_once_with(
            symbol='ETH/BTC', type='limit', side='sell', amount=0.00034843, price=0.035750000000000004
        )
        assert_equal(self.exchange.fetch_order_status.call_count, 2)
        self.exchange.cancel_order.assert_called_once_with(id=33, symbol='ETH/BTC')

    async def test_execute_till_on_binance_handles_no_order_exception(self) -> None:
        self.exchange.fetch_order_status.side_effect = mocked_cancel_order_filled_response
        command = ExchangeAllCurrency(self.exchange, 'ETH', 'BTC', execute_till=0.7)
        with assert_raises(PostConditionError):
            await execute_commands(command)
        self.exchange.create_order.assert_called_once_with(
            symbol='ETH/BTC', type='limit', side='sell', amount=0.00034843, price=0.035750000000000004
        )
        assert_equal(self.exchange.fetch_order_status.call_count, 1)
        self.exchange.cancel_order.assert_not_called()

    async def test_sell_position_command_execution_amount_in_usd_currency(self) -> None:
        command = SellPosition(self.exchange, 'ETH-0625', amount=4, in_currency='USD')
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {PositionCondition(self.exchange, 'ETH-0625', '<', -4.242)})

        assert_equal(self.exchange.fetch_balance.call_count, 0)
        calls = [call(symbols={'ETH/USD', 'ETH-0625'}),
                 call(symbols={'ETH-0625'})]
        self.exchange.fetch_tickers.assert_has_calls(calls)
        self.exchange.create_order.assert_called_once_with(symbol='ETH-0625', type='market', side='sell',
                                                           amount=0.0024600246002460025, params={})

    async def test_sell_position_command_execution_amount_in_future_price(self) -> None:
        command = SellPosition(self.exchange, 'ETH-0625', amount=1)
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {PositionCondition(self.exchange, 'ETH-0625', '<', -4.242)})

        assert_equal(self.exchange.fetch_balance.call_count, 0)
        calls = [call(symbols={'ETH-0625'}),
                 call(symbols={'ETH-0625'})]
        self.exchange.fetch_tickers.assert_has_calls(calls)
        self.exchange.create_order.assert_called_once_with(symbol='ETH-0625', type='market', side='sell',
                                                           amount=1, params={})

    async def test_sell_position_command_execution_amount_in_eth_currency(self) -> None:
        command = SellPosition(self.exchange, 'ETH-0625', amount=1, in_currency='ETH')
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {PositionCondition(self.exchange, 'ETH-0625', '<', -4.242)})

        assert_equal(self.exchange.fetch_balance.call_count, 0)
        calls = [call(symbols={'ETH/USD', 'ETH-0625'}),
                 call(symbols={'ETH-0625'})]
        self.exchange.fetch_tickers.assert_has_calls(calls)
        self.exchange.create_order.assert_called_once_with(symbol='ETH-0625', type='market', side='sell',
                                                           amount=0.9384993849938499, params={})

    async def test_buy_position_command_execution_amount_in_usd_currency(self) -> None:
        command = BuyPosition(self.exchange, 'ETH-0625', amount=4, in_currency='USD')
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {PositionCondition(self.exchange, 'ETH-0625', '>', -4.242)})

        assert_equal(self.exchange.fetch_balance.call_count, 0)
        calls = [call(symbols={'ETH/USD', 'ETH-0625'}),
                 call(symbols={'ETH-0625'})]
        self.exchange.fetch_tickers.assert_has_calls(calls)
        self.exchange.create_order.assert_called_once_with(symbol='ETH-0625', type='market', side='buy',
                                                           amount=0.0024602226437088824,
                                                           params={'reduceOnly': False})

    async def test_buy_position_command_execution_amount_in_future_price(self) -> None:
        command = BuyPosition(self.exchange, 'ETH-0625', amount=1)
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {PositionCondition(self.exchange, 'ETH-0625', '>', -4.242)})

        assert_equal(self.exchange.fetch_balance.call_count, 0)
        calls = [call(symbols={'ETH-0625'}),
                 call(symbols={'ETH-0625'})]
        self.exchange.fetch_tickers.assert_has_calls(calls)
        self.exchange.create_order.assert_called_once_with(symbol='ETH-0625', type='market', side='buy',
                                                           amount=1, params={'reduceOnly': False})

    async def test_buy_position_command_execution_amount_in_eth_currency(self) -> None:
        command = BuyPosition(self.exchange, 'ETH-0625', amount=1, in_currency='ETH')
        with assert_raises(PostConditionError) as cm:
            await execute_commands(command)
        assert_equal(cm.exception.failed_conditions,
                     {PositionCondition(self.exchange, 'ETH-0625', '>', -4.242)})

        assert_equal(self.exchange.fetch_balance.call_count, 0)
        calls = [call(symbols={'ETH/USD', 'ETH-0625'}),
                 call(symbols={'ETH-0625'})]
        self.exchange.fetch_tickers.assert_has_calls(calls)
        self.exchange.create_order.assert_called_once_with(symbol='ETH-0625', type='market', side='buy',
                                                           amount=0.9385749385749386,
                                                           params={'reduceOnly': False})
