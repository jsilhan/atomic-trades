import asyncio
from typing import Set

import pytest

from atomic_trades.commands import BaseCommand
from atomic_trades.conditions import BalanceCondition, BaseCCXTCall
from atomic_trades.exceptions import InvalidConditionComparatorError
from atomic_trades.functions import evaluate_pre_conditions
from atomic_trades.utils import get_currency_balance
from tests.base import BALANCE_DATA, BaseTestCase


def async_return(result):
    f = asyncio.Future()
    f.set_result(result)
    return f


class MockTrueConditionsCommand(BaseCommand):

    def pre_conditions(self) -> Set[BaseCCXTCall]:
        return {
            BalanceCondition(self.exchange, 'USD', 'gte', 68),
            BalanceCondition(self.exchange, 'ETH', 'gte', 0.0003),
        }


class MockFalseConditionsCommand(BaseCommand):

    def pre_conditions(self) -> Set[BaseCCXTCall]:
        return {
            BalanceCondition(self.exchange, 'USD', 'gte', 68),
            BalanceCondition(self.exchange, 'LTC', 'gte', 76),
        }


class ConditionTestCase(BaseTestCase):

    def setUp(self) -> None:
        self.exchange = self.create_mocked_exchange(name='FTX')
        self.exchange2 = self.create_mocked_exchange(name='Binance')

    async def test_one_success_one_failure_one_call(self) -> None:
        successful_conditions, failed_conditions = await evaluate_pre_conditions(
            MockTrueConditionsCommand(self.exchange),
            MockFalseConditionsCommand(self.exchange)
        )
        self.exchange.fetch_balance.assert_called_once_with()
        self.exchange.fetch_tickers.assert_not_called()
        assert successful_conditions == {BalanceCondition(self.exchange, 'USD', '>=', 68),
                                         BalanceCondition(self.exchange, 'ETH', '>=', 0.0003)}
        assert failed_conditions == {BalanceCondition(self.exchange, 'LTC', 'gte', 76)}

    async def test_one_success(self) -> None:
        successful_conditions, failed_conditions = await evaluate_pre_conditions(
            MockTrueConditionsCommand(self.exchange))
        assert successful_conditions == {BalanceCondition(self.exchange, 'USD', 'gte', 68),
                                         BalanceCondition(self.exchange, 'ETH', 'gte', 0.0003)}
        assert failed_conditions == set()

    async def test_one_call_per_exchange(self) -> None:
        await evaluate_pre_conditions(
            MockTrueConditionsCommand(self.exchange),
            MockFalseConditionsCommand(self.exchange2),
        )
        self.exchange.fetch_balance.assert_called_once()
        self.exchange.fetch_tickers.assert_not_called()
        self.exchange2.fetch_balance.assert_called_once()
        self.exchange2.fetch_tickers.assert_not_called()

    async def test_condition_not_satisfied_when_no_balance(self) -> None:
        condition = BalanceCondition(self.exchange, 'SPX', 'gt', 0)
        command = self.create_command(self.exchange, pre_conditions={condition})
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        assert successful_conditions == set()
        assert failed_conditions == {condition}

    async def test_raises_invalid_comparator_error(self) -> None:
        condition = BalanceCondition(self.exchange, 'LTC', 'invalid_operator', 13125)
        command = self.create_command(self.exchange, pre_conditions={condition})
        with pytest.raises(InvalidConditionComparatorError):
            await evaluate_pre_conditions(command)

    async def test_str_balance(self) -> None:
        assert str(BalanceCondition(self.exchange, 'USD', 'gte', 68)) == "BalanceCondition: USD balance >= 68 on FTX"

    async def test_str_balance_in_base_currency(self) -> None:
        assert str(BalanceCondition(self.exchange, 'USD', 'gte', 68, in_currency='USD')) == (
            "BalanceCondition: USD balance >= 68 on FTX"
        )

    async def test_str_balance_in_different_currency(self) -> None:
        assert str(BalanceCondition(self.exchange, 'LTC', 'gte', 68, in_currency='USD')) == (
            "BalanceCondition: LTC balance >= 68 USD on FTX"
        )

    async def test_sufficient_balance_conversion(self) -> None:
        condition = BalanceCondition(self.exchange, 'LTC', 'gte', 13125, in_currency='USD')
        command = self.create_command(self.exchange, pre_conditions={condition})
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        self.exchange.fetch_balance.assert_called_once()
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'LTC/USD'})
        assert successful_conditions == {condition}
        assert failed_conditions == set()

    async def test_insufficient_balance_conversion(self) -> None:
        condition = BalanceCondition(self.exchange, 'LTC', 'gte', 20000, in_currency='USD')
        command = self.create_command(self.exchange, pre_conditions={condition})
        successful_conditions, failed_conditions = await evaluate_pre_conditions(command)
        self.exchange.fetch_balance.assert_called_once()
        self.exchange.fetch_tickers.assert_called_once_with(symbols={'LTC/USD'})
        assert failed_conditions == {condition}
        assert successful_conditions == set()

    async def test_balance_is_taken_from_free_funds(self) -> None:
        condition = BalanceCondition(self.exchange, 'BTC', 'gte', 2)
        command = self.create_command(self.exchange, pre_conditions={condition})
        _, failed_conditions = await evaluate_pre_conditions(command)
        assert failed_conditions == {condition}
        assert get_currency_balance(command.pre_condition_responses, 'BTC') == BALANCE_DATA['free']['BTC']
