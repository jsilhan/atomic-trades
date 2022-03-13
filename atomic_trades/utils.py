import asyncio
import re
from typing import Any, Dict, Optional, Union

from ccxt.base.errors import OrderNotFound
from ccxt.base.exchange import Exchange

from atomic_trades.exceptions import MarketDoesNotExistsError

spot_symbol_regexp = re.compile('^([A-Z]+)')


def get_currency_balance(ccxt_responses: Dict[str, Any], currency: str) -> Union[int, float]:
    return ccxt_responses['fetch_balance']['free'].get(currency, 0.0)


def get_position_size(ccxt_responses: Dict[str, Any], symbol: str) -> float:
    for response in ccxt_responses['fetch_positions']:
        if response['future'] == symbol:
            return float(response['netSize'])
    return 0.0


def get_currency_from_symbol(symbol: str) -> str:
    match = spot_symbol_regexp.match(symbol)
    if not match:
        raise MarketDoesNotExistsError(f'Cannot parse currency from symbol {symbol}')
    return match.group(1)


async def wait_till_order_closed(exchange: Exchange, order_id: int, timeout: float, symbol: Optional[str] = None,
                                 polling_interval: float = 0.3) -> bool:
    async def order_state_polling():
        while 1:
            await asyncio.sleep(polling_interval)
            try:
                if await exchange.fetch_order_status(order_id, symbol=symbol) != 'open':
                    break
            except OrderNotFound:
                break
    try:
        await asyncio.wait_for(order_state_polling(), timeout)
        return True
    except asyncio.TimeoutError:
        return False
