# Atomic Trades

Atomic Trades library provides easy handling of multiple orders that have to be executed all together or none of them.
The library makes sure all conditions are met in advance to execute all trades and does another check after orders are filled. The goal is also to reduce redundant calls to exchanges and execute calls to the exchanges in asynchronous way without the need to specify it manually and avoid complexity when dealing with many exchanges and many orders. The intuitive currency conversion is supported by all the commands.
It uses CCXT library for crypto trading but it could also support connection to stock exchanges if new commands and conditions are implemented.


# Examples

### Capturing spot market arbitrage opportunity across multiple exchanges
Suppose we have found an arbitrage opportunity across 3 exchanges. To take advantage of that and to profit we have to:
* buy XRP on XRP/ETH market on Binance
* buy BTC on XRP/BTC market on FTX
* buy ETH on ETH/BTC market on OKEx

To make orders with the same amount (50 USD) on different exchanges:
```python
import ccxt.async_support
from atomic_trades.commands import *
from atomic_trades.functions import execute_commands

ftx = ccxt.async_support.ftx(**ftx_credentials)
binance = ccxt.async_support.binance(**binance_credentials)
okex = ccxt.async_support.okex(**okex_credentials)

await execute_commands(
    ExchangeCurrency(binance, from_currency='ETH', to_currency='XRP', amount=50, in_currency='USD'),
    ExchangeCurrency(ftx, from_currency='XRP', to_currency='BTC', amount=50, in_currency='USD'),
    ExchangeCurrency(okex, from_currency='ETH', to_currency='BTC', amount=50, in_currency='USD')
)
```

The library will proceed with the following steps:
1. async CCXT calls to get available balance and ticker prices for currency conversions
2. currency conversions processing + evaluation of available balance conditions on all exchanges (can raise error with all unsatisfied conditions)
3. async execution of all orders / positions
4. async CCXT calls to get updated available balance on exchanges
5. checks that balance has been changed according to the trades (can raise error with all unsatisfied conditions)

### Making cash and carry arbitrage trade
Let's imagine we have found different price of the BTC future and price of the asset on OKEx exchange.

`BTC/USDT` ticker price is 68554

`BTC-USDT-220325` future symbol price is 72722

There's a 6.1% price difference and we know the price will convert to the same amount at the end.
The strategy is to buy an asset and short a more expensive future and hold it till the future expiration date or till the time when the spread between the future and asset significantly decreases.

```python
await execute_commands(
    ExchangeCurrency(okex, from_currency='USDT', to_currency='BTC', amount=50, in_currency='USDT'),
    SellPosition(okex, symbol='BTC-USDT-220325', amount=50, in_currency='USD')
)
```
To exit the trade you can run:
```python
await execute_commands(
    ExchangeAllCurrency(okex, from_currency='BTC', to_currency='USDT'),
    ClosePosition(okex, symbol='BTC-USDT-220325')
)
```
For larger amount to avoid slippage execute a few times:
```python
await execute_commands(
    ExchangeCurrency(okex, from_currency='BTC', to_currency='USDT', amount=50, in_currency='USDT'),
    BuyPosition(okex, symbol='BTC-USDT-220325', amount=50, in_currency='USDT')
)
```
For more examples please take a look inside `/tests` directory.

# Installation
`pip install -e git://github.com/jsilhan/atomic-trades.git#egg=atomic-trades`


# Disclaimer
The Atomic Trades library should work on any exchange supported by CCXT but there could be small API behavior nuances on different exchanges especially when cancelling partially filled orders. The library has been tested on Binance, OKEx and FTX.

Currently there's no websocket CCXT Pro support.
