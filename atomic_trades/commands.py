from typing import Any, Dict, Optional, Set, Union

from ccxt.base.errors import InvalidOrder, OrderNotFound
from ccxt.base.exchange import Exchange

from atomic_trades.conditions import (BalanceCondition, BaseCCXTCall,
                                      CurrencyConversion, PositionCondition,
                                      PositionFetch)
from atomic_trades.utils import (get_currency_balance,
                                 get_currency_from_symbol,
                                 wait_till_order_closed)


class BaseCommand:

    # responses from ccxt methods, {'<ccxt method name>': <json ccxt method response>}
    pre_condition_responses: Dict[str, Any] = {}
    post_condition_responses: Dict[str, Any] = {}

    def __init__(self, exchange: Exchange) -> None:
        self.exchange = exchange

    def __repr__(self):
        return str(self)

    def pre_conditions(self) -> Set[BaseCCXTCall]:
        return set()

    async def execute(self):
        raise NotImplementedError

    def post_conditions(self):
        return set()


class ExecuteOrderTillCommand(BaseCommand):

    LIMIT_ORDER_PORTION_FROM_SPREAD = 2

    def set_timeout(self, execute_till: Union[int, float]) -> None:
        assert execute_till is None or execute_till >= 0, \
            f'execute_till must be positive number, zero or None, {execute_till} given'
        self.execute_till = execute_till

    async def create_limit_order_with_timeout(self, trading_side: str, symbol: str, amount: Union[int, float],
                                              params: Optional[Dict[str, bool]] = None) -> None:
        timeout = self.execute_till
        if timeout != 0:
            # create limit order, wait and then create market taker order if it has not been executed yet
            ticker = self.pre_condition_responses['fetch_tickers'][symbol]
            spread = ticker['ask'] - ticker['bid']
            portion_above_last_price = spread / self.LIMIT_ORDER_PORTION_FROM_SPREAD
            limit_price = (
                ticker['bid'] + portion_above_last_price if trading_side == 'buy'
                else ticker['ask'] - portion_above_last_price
            )
            order_response = await self.exchange.create_order(
                symbol=symbol, type='limit', side=trading_side, amount=amount, price=limit_price
            )
            if timeout is None:
                return
            if await wait_till_order_closed(self.exchange, order_response['id'], timeout=timeout, symbol=symbol):
                return
            else:
                try:
                    await self.exchange.cancel_order(id=order_response['id'], symbol=symbol)
                except (OrderNotFound, InvalidOrder):
                    # order was already executed
                    return
                order_response = await self.exchange.fetch_order(id=order_response['id'])
                if order_response['filled'] > 0:
                    amount = amount - order_response['filled']
        # create marker taker order
        await self.exchange.create_order(symbol=symbol, type='market', side=trading_side, amount=amount,
                                         params=params or {})


class BaseExchangeCurrencyCommand(ExecuteOrderTillCommand):

    def __init__(self, exchange: Exchange, from_currency: str, to_currency: str,
                 execute_till: Union[int, float]) -> None:
        super().__init__(exchange)
        self.set_timeout(execute_till)
        self.to_currency = to_currency
        self.from_currency = from_currency

    def initial_currency_balance(self, currency: str) -> Union[int, float]:
        return get_currency_balance(self.pre_condition_responses, currency)

    def post_conditions(self) -> Set[BaseCCXTCall]:
        return {
            BalanceCondition(self.exchange, self.from_currency, '<', self.initial_currency_balance(self.from_currency)),
            BalanceCondition(self.exchange, self.to_currency, '>', self.initial_currency_balance(self.to_currency))
        }


class ExchangeAllCurrency(BaseExchangeCurrencyCommand):

    def __init__(self, exchange: Exchange, from_currency: str, to_currency: str,
                 execute_till: Union[int, float] = 0) -> None:
        super().__init__(exchange, from_currency, to_currency, execute_till)
        self.selling_currency_balance_condition = BalanceCondition(self.exchange, self.from_currency, '>', 0,
                                                                   in_currency=self.to_currency)

    def __str__(self):
        return f'{self.__class__.__name__}: exchange all {self.from_currency} to {self.to_currency}'

    def pre_conditions(self) -> Set[BaseCCXTCall]:
        return {self.selling_currency_balance_condition}

    async def execute(self) -> None:
        symbol = self.selling_currency_balance_condition.converting_symbol
        if self.selling_currency_balance_condition.is_symbol_reversed:
            trading_side = 'sell'
            amount = self.initial_currency_balance(self.from_currency)
        else:
            trading_side = 'buy'
            amount = self.selling_currency_balance_condition.balance_amount_in_currency
        await self.create_limit_order_with_timeout(trading_side=trading_side, symbol=symbol, amount=amount)


class ExchangeCurrency(BaseExchangeCurrencyCommand):

    def __init__(self, exchange: Exchange, from_currency: str, to_currency: str, amount: int,
                 in_currency: Optional[str] = None, execute_till: int = 0, margin: bool = False) -> None:
        assert amount > 0, f'amount must be positive number, {amount} given'
        super().__init__(exchange, from_currency, to_currency, execute_till)
        self.amount = amount
        self.in_currency = None if self.to_currency == in_currency else in_currency
        self.margin = margin
        # just to compute the trading symbol, no need to put it into pre conditions to fetch tickers
        self.trading_symbol_conversion = CurrencyConversion(
            self.exchange, from_currency=self.from_currency, to_currency=self.to_currency
        )
        if self.trading_symbol_conversion.is_symbol_reversed:
            self.buying_currency_conversion = CurrencyConversion(
                self.exchange, from_currency=self.in_currency or self.to_currency, to_currency=self.from_currency
            )
        else:
            self.buying_currency_conversion = CurrencyConversion(
                self.exchange, from_currency=self.in_currency or self.to_currency, to_currency=self.to_currency
            )

    def __str__(self):
        in_currency_string = f' {self.in_currency} from' if self.in_currency else ''
        return (
            f'{self.__class__.__name__}: exchange {self.amount}{in_currency_string} '
            f'{self.from_currency} to {self.to_currency}'
        )

    def pre_conditions(self) -> Set[BaseCCXTCall]:
        conditions = {self.buying_currency_conversion}
        if not self.margin:
            self.selling_currency_balance_condition = BalanceCondition(
                self.exchange, self.from_currency, '>=', self.amount, in_currency=self.in_currency or self.to_currency
            )
            conditions.add(self.selling_currency_balance_condition)
        return conditions

    async def execute(self) -> None:
        amount_in_buying_currency = self.buying_currency_conversion.convert_amount(self.amount)
        trading_side = 'sell' if self.trading_symbol_conversion.is_symbol_reversed else 'buy'
        await self.create_limit_order_with_timeout(
            trading_side=trading_side, symbol=self.trading_symbol_conversion.converting_symbol,
            amount=amount_in_buying_currency
        )


class BuyPosition(ExecuteOrderTillCommand):

    def __init__(self, exchange: Exchange, symbol: str, amount: int, in_currency: Optional[str] = None,
                 execute_till: int = 0, reduce_only: bool = False) -> None:
        super().__init__(exchange)
        assert amount > 0, f'amount must be positive number, {amount} given'
        self.set_timeout(execute_till)
        self.to_currency = get_currency_from_symbol(symbol)
        self.in_currency = in_currency
        self.amount = amount
        self.reduce_only = reduce_only
        self.symbol_position = PositionFetch(exchange, symbol)
        self.buying_currency_conversion = CurrencyConversion(
            self.exchange, from_currency=in_currency or self.to_currency, to_currency=self.to_currency
        )
        self.spot_usd_conversion = CurrencyConversion(self.exchange, from_currency='USD', to_currency=self.to_currency)

    def __str__(self):
        currency = self.in_currency or self.to_currency
        return (
            f'{self.__class__.__name__}: sell {self.amount}{currency} in {self.symbol_position.symbol} position'
        )

    def pre_conditions(self) -> Set[BaseCCXTCall]:
        conditions = {self.symbol_position, self.buying_currency_conversion}
        if self.in_currency:
            conditions.add(self.spot_usd_conversion)
        if self.reduce_only:
            conditions.add(PositionCondition(self.exchange, self.symbol_position.symbol, '<=', -self.amount,
                                             in_currency=self.in_currency))
        return conditions

    async def execute(self) -> None:
        if self.in_currency:
            fetch_tickers_response = self.pre_condition_responses['fetch_tickers']
            amount_in_buying_currency = self.buying_currency_conversion.convert_amount(self.amount) * (
                fetch_tickers_response[self.spot_usd_conversion.converting_symbol]['ask'] /
                fetch_tickers_response[self.symbol_position.symbol]['ask']
            )
        else:
            amount_in_buying_currency = self.amount
        await self.create_limit_order_with_timeout(
            trading_side='buy', symbol=self.symbol_position.symbol, amount=amount_in_buying_currency,
            params={'reduceOnly': self.reduce_only}
        )

    def post_conditions(self) -> Set[BaseCCXTCall]:
        initial_position_amount = self.symbol_position.position_amount_in_currency
        return {PositionCondition(self.exchange, self.symbol_position.symbol, '>', initial_position_amount)}


class SellPosition(ExecuteOrderTillCommand):

    def __init__(self, exchange: Exchange, symbol: str, amount: int, in_currency: Optional[str] = None,
                 execute_till: int = 0) -> None:
        super().__init__(exchange)
        assert amount > 0, f'amount must be positive number, {amount} given'
        self.set_timeout(execute_till)
        self.to_currency = get_currency_from_symbol(symbol)
        self.in_currency = in_currency
        self.amount = amount
        self.symbol_position = PositionFetch(exchange, symbol)
        self.selling_currency_conversion = CurrencyConversion(
            self.exchange, from_currency=in_currency or self.to_currency, to_currency=self.to_currency
        )
        self.spot_usd_conversion = CurrencyConversion(self.exchange, from_currency='USD', to_currency=self.to_currency)

    def __str__(self):
        currency = self.in_currency or self.to_currency
        return (
            f'{self.__class__.__name__}: sell {self.amount}{currency} in {self.symbol_position.symbol} position'
        )

    def pre_conditions(self) -> Set[BaseCCXTCall]:
        conditions = {self.symbol_position, self.selling_currency_conversion}
        if self.in_currency:
            conditions.add(self.spot_usd_conversion)
        return conditions

    async def execute(self) -> None:
        if self.in_currency:
            fetch_ticker_response = self.pre_condition_responses['fetch_tickers']
            amount_in_buying_currency = self.selling_currency_conversion.convert_amount(self.amount) * (
                fetch_ticker_response[self.spot_usd_conversion.converting_symbol]['bid'] /
                fetch_ticker_response[self.symbol_position.symbol]['bid']
            )
        else:
            amount_in_buying_currency = self.amount
        await self.create_limit_order_with_timeout(
            trading_side='sell', symbol=self.symbol_position.symbol, amount=amount_in_buying_currency
        )

    def post_conditions(self) -> Set[BaseCCXTCall]:
        initial_position_amount = self.symbol_position.position_amount_in_currency
        return {PositionCondition(self.exchange, self.symbol_position.symbol, '<', initial_position_amount)}


class ClosePosition(ExecuteOrderTillCommand):

    def __init__(self, exchange, symbol, execute_till=0):
        super().__init__(exchange)
        self.set_timeout(execute_till)
        self.symbol_position_condition = PositionCondition(exchange, symbol, '!=', 0)

    def __str__(self):
        return (
            f'{self.__class__.__name__}: close entire {self.symbol_position_condition.symbol} position'
        )

    def pre_conditions(self) -> Set[BaseCCXTCall]:
        return {self.symbol_position_condition}

    async def execute(self):
        amount = self.symbol_position_condition.position_amount_in_currency
        trading_side = 'sell' if amount > 0 else 'buy'
        await self.create_limit_order_with_timeout(
            trading_side=trading_side, symbol=self.symbol_position_condition.symbol, amount=abs(amount)
        )

    def post_conditions(self) -> Set[BaseCCXTCall]:
        return {PositionCondition(self.exchange, self.symbol_position_condition.symbol, '==', 0)}
