from atomic_trades.exceptions import (InvalidConditionComparatorError,
                                      MarketDoesNotExistsError)
from atomic_trades.utils import (get_currency_balance, get_currency_from_symbol,
                                 get_position_size)


class BaseCCXTCall:

    def __repr__(self):
        return str(self)

    def ccxt_methods(self):
        return {}


class BaseCondition(BaseCCXTCall):

    comparator_map = {
        'gte': '>=',
        'gt': '>',
        'lte': '<=',
        'lt': '<',
        'eq': '==',
        'neq': '!=',
    }

    def __init__(self, exchange, comparator, comparable_value, *args):
        self.exchange = exchange
        self.comparator = self.comparator_map[comparator] if comparator in self.comparator_map else comparator
        self.comparable_value = comparable_value
        self._additional_hashable_params = args

    def __eq__(self, other):
        return (
            self.__class__.__name__ == other.__class__.__name__ and self.exchange == other.exchange
            and self._additional_hashable_params == other._additional_hashable_params
            and self.comparator == other.comparator and self.comparable_value == other.comparable_value
        )

    def __hash__(self):
        return hash((self.__class__.__name__, self.exchange, self._additional_hashable_params, self.comparator,
                     self.comparable_value))

    def _compare(self, current, comparator, threshold_value):
        if comparator == '>':
            return current > threshold_value
        elif comparator == '>=':
            return current >= threshold_value
        if comparator == '<':
            return current < threshold_value
        elif comparator == '<=':
            return current <= threshold_value
        elif comparator == '==':
            return current == threshold_value
        elif comparator == '!=':
            return current != threshold_value
        else:
            raise InvalidConditionComparatorError(f'Invalid comparator type {comparator}')

    def evaluate(self, responses):
        raise NotImplementedError


class CurrencyConversionMixin:

    def set_from_to_currency(self, from_currency, to_currency):
        # should be called in __init__ method
        self.from_currency = from_currency
        self.to_currency = to_currency
        self.converting_symbol, self.is_symbol_reversed = self._get_converting_symbol_and_reversed()

    def _get_converting_symbol_and_reversed(self):
        if self.from_currency == self.to_currency:
            return None, False
        symbol = f'{self.to_currency}/{self.from_currency}'
        if symbol in self.exchange.markets:
            return symbol, False
        reversed_symbol = f'{self.from_currency}/{self.to_currency}'
        if reversed_symbol in self.exchange.markets:
            return reversed_symbol, True
        else:
            raise MarketDoesNotExistsError(
                f'Cannot find ticker to convert {self.from_currency} currency to {self.to_currency} currency'
            )

    def convert_amount(self, amount, responses=None):
        if self.from_currency == self.to_currency:
            return amount
        responses = responses or self.responses
        fetched_symbol = responses['fetch_tickers'][self.converting_symbol]
        if self.is_symbol_reversed:
            return amount * fetched_symbol['ask']
        else:
            return (1 / fetched_symbol['bid']) * amount


class CurrencyConversion(CurrencyConversionMixin, BaseCCXTCall):

    def __init__(self, exchange, from_currency, to_currency):
        self.exchange = exchange
        self.set_from_to_currency(from_currency, to_currency)

    def __str__(self):
        return (
            f'{self.__class__.__name__}: {self.from_currency} -> {self.to_currency} on {self.exchange.name}'
        )

    def ccxt_methods(self):
        return {
            'fetch_tickers': {'symbols': {self.converting_symbol}}
        } if self.from_currency != self.to_currency else {}

    def evaluate(self, responses):
        self.responses = responses
        return None


class BalanceCondition(CurrencyConversionMixin, BaseCondition):

    def __init__(self, exchange, currency, comparator, comparable_value, in_currency=None):
        self.in_currency = None if in_currency == currency else in_currency
        super().__init__(exchange, comparator, comparable_value, currency, self.in_currency)
        self.currency = currency
        self.set_from_to_currency(currency, in_currency or currency)

    def __str__(self):
        in_currency_string = f' {self.in_currency}' if self.in_currency else ''
        return (
            f'{self.__class__.__name__}: {self.currency} balance {self.comparator} '
            f'{self.comparable_value}{in_currency_string} on {self.exchange.name}'
        )

    def ccxt_methods(self):
        methods = {
            'fetch_balance': {}
        }
        if self.in_currency:
            methods['fetch_tickers'] = {'symbols': {self.converting_symbol}}
        return methods

    def evaluate(self, responses):
        self.responses = responses
        self.balance_amount_in_currency = self.convert_amount(get_currency_balance(responses, self.currency))
        return self._compare(self.balance_amount_in_currency, self.comparator, self.comparable_value)


class PositionFetch(CurrencyConversionMixin, BaseCCXTCall):

    def __init__(self, exchange, symbol, in_currency=None):
        self.currency = get_currency_from_symbol(symbol)
        self.in_currency = None if self.currency else in_currency
        self.exchange = exchange
        self.symbol = symbol
        self.set_from_to_currency(self.currency, in_currency or self.currency)

    def ccxt_methods(self):
        methods = {
            'fetch_positions': {'symbols': {self.symbol}}
        }
        symbols = {self.symbol}
        if self.in_currency:
            symbols.add(self.converting_symbol)
        methods['fetch_tickers'] = {'symbols': symbols}
        return methods

    def evaluate(self, responses):
        self.responses = responses
        self.position_amount_in_currency = self.convert_amount(get_position_size(responses, self.symbol))
        return None


class PositionCondition(BaseCondition, PositionFetch):

    def __init__(self, exchange, symbol, comparator, comparable_value, in_currency=None):
        self.currency = get_currency_from_symbol(symbol)
        self.in_currency = None if self.currency else in_currency
        super().__init__(exchange, comparator, comparable_value, symbol, self.in_currency)
        self.symbol = symbol
        self.set_from_to_currency(self.currency, in_currency or self.currency)

    def __str__(self):
        return (
            f'{self.__class__.__name__}: {self.symbol} position size {self.comparator} '
            f'{self.comparable_value} {self.in_currency or self.currency} on {self.exchange.name}'
        )

    def evaluate(self, responses):
        self.responses = responses
        self.position_amount_in_currency = self.convert_amount(get_position_size(responses, self.symbol))
        return self._compare(self.position_amount_in_currency, self.comparator, self.comparable_value)
