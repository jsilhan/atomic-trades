import asyncio
from collections import defaultdict
from typing import (Any, DefaultDict, Dict, Iterator, List, Optional, Sequence,
                    Set, Tuple)

from ccxt.base.exchange import Exchange
from mergedeep import Strategy, merge

from atomic_trades.commands import BaseCommand
from atomic_trades.conditions import BaseCCXTCall, BaseCondition
from atomic_trades.exceptions import (CommandExecutionError,
                                      PostConditionError, PreConditionError)

__all__ = (
    'evaluate_pre_conditions',
    'execute_commands',
    'human_execute_commands_in_sequence'
)


def _get_aggregated_ccxt_method_calls(conditions_map: DefaultDict[Exchange, Set[BaseCCXTCall]]
                                      ) -> Dict[Exchange, Dict[str, Any]]:
    ccxt_exchange_methods_map: Dict[Exchange, Dict[str, Dict[str, Any]]] = {}
    for exchange, conditions in conditions_map.items():
        ccxt_methods_map: Dict[str, Dict[str, Any]] = {}
        for condition in conditions:
            # CCXT method will be called just once with parameters aggregated from other conditions
            merge(ccxt_methods_map, condition.ccxt_methods(), strategy=Strategy.ADDITIVE)
        ccxt_exchange_methods_map[exchange] = ccxt_methods_map
    return ccxt_exchange_methods_map


def _get_conditions_map(commands: Any, condition_type: str) -> DefaultDict[Exchange, Set[BaseCCXTCall]]:
    conditions_map: DefaultDict[Exchange, Set[BaseCCXTCall]] = defaultdict(set)
    for command in commands:
        conditions = getattr(command, f'{condition_type}_conditions')()
        conditions_map[command.exchange].update(conditions)
    return conditions_map


def _exchange_method_iterator(method_calls_map: Dict[Exchange, Dict[str, Dict[str, Any]]]
                              ) -> Iterator[Tuple[Exchange, str, Dict[str, Any]]]:
    for exchange, method_calls in method_calls_map.items():
        for method_name, method_params in method_calls.items():
            yield (exchange, method_name, method_params)


async def _get_ccxt_response(exchange: Exchange, method_name: str, method_params: Dict[str, Any]
                             ) -> Tuple[Exchange, str, Any]:
    if not exchange.markets:
        await exchange.load_markets()
    response = await getattr(exchange, method_name)(**method_params)
    return (exchange, method_name, response)


async def _get_parallel_pre_condition_responses(method_calls_map: Dict[Exchange, Dict[str, Any]]
                                                ) -> List[Tuple[Exchange, str, Dict[str, Any]]]:
    tasks = [_get_ccxt_response(exchange, method_name, method_params)
             for exchange, method_name, method_params in _exchange_method_iterator(method_calls_map)]
    return await asyncio.gather(*tasks, return_exceptions=False)


def _evaluate_conditions_from_responses(condition_responses_map: DefaultDict[Exchange, Dict[str, Any]],
                                        conditions_map: DefaultDict[Exchange, Set[BaseCondition]]
                                        ) -> Tuple[Set[BaseCondition], Set[BaseCondition]]:
    successful = set()
    failed = set()
    for exchange, conditions in conditions_map.items():
        for condition in conditions:
            result = condition.evaluate(condition_responses_map[exchange])
            if result is True:
                successful.add(condition)
            elif result is False:
                failed.add(condition)
            # result with None is not a condition and is ignored in successful/failed lists
    return successful, failed


async def _evaluate_conditions(commands: Sequence[BaseCommand], condition_type: str
                               ) -> Tuple[Set[BaseCondition], Set[BaseCondition]]:
    conditions_map = _get_conditions_map(commands, condition_type)
    method_calls_map = _get_aggregated_ccxt_method_calls(conditions_map)

    responses = await _get_parallel_pre_condition_responses(method_calls_map)

    condition_responses_map: DefaultDict[Exchange, Dict[str, Any]] = defaultdict(dict)
    for (exchange, method_name, response) in responses:
        condition_responses_map[exchange][method_name] = response

    successful, failed = _evaluate_conditions_from_responses(condition_responses_map, conditions_map)

    # append condition results into commands
    for command in commands:
        setattr(command, f'{condition_type}_condition_responses', condition_responses_map[command.exchange])

    return successful, failed


async def _get_command_futures(commands: Sequence[BaseCommand]) -> List[Optional[Exception]]:
    return await asyncio.gather(
        *[command.execute() for command in commands], return_exceptions=True
    )


async def _execute_commands_or_raise_error(commands: Sequence[BaseCommand]) -> None:
    results = await _get_command_futures(commands)
    failed_commands_dict = {}
    for command, error in zip(commands, results):
        if issubclass(error.__class__, Exception):
            failed_commands_dict[command] = error
    if failed_commands_dict:
        raise CommandExecutionError(failed_commands_dict=failed_commands_dict)


async def evaluate_pre_conditions(*commands: BaseCommand) -> Tuple[Set[BaseCondition], Set[BaseCondition]]:
    return await _evaluate_conditions(commands, 'pre')


async def execute_commands(*commands: BaseCommand, post_conditions_delay: float = 0.4):
    _, failures = await evaluate_pre_conditions(*commands)
    if failures:
        raise PreConditionError(failed_conditions=failures)

    await _execute_commands_or_raise_error(commands)

    # sometimes exchange haven't updated balance after command executions yet
    await asyncio.sleep(post_conditions_delay)

    _, failures = await _evaluate_conditions(commands, 'post')
    if failures:
        raise PostConditionError(failed_conditions=failures)


async def human_execute_commands_in_sequence(*command_batches: Sequence[BaseCommand], count: int = 1,
                                             sleep_secs: float = 0.4, fail_on_first_batch_precondition: bool = False,
                                             fail_on_postconditions: bool = True):
    for execution_count in range(1, count + 1):
        print(f'{execution_count}. execution round started:')
        for batch_count, commands in enumerate(command_batches, start=1):
            while 1:
                try:
                    await execute_commands(*commands)
                    print(f'  {batch_count}. batch executed successfully.')
                    break
                except PreConditionError as e:
                    if batch_count == 1 and not fail_on_first_batch_precondition:
                        print(f'  {batch_count}. batch failed on pre conditions, repeating...',
                              e.failed_conditions)
                        continue
                    print(f'  {batch_count}. batch failed on pre conditions:', e.failed_conditions)
                    return
                except PostConditionError as e:
                    print(f'  {batch_count}. batch executed and failed on post conditions:', e.failed_conditions)
                    if not fail_on_postconditions:
                        break
                    return
                except CommandExecutionError as e:
                    print(f'  {batch_count}. batch executed, failed during execution:', e.failed_commands_dict)
                    return
            await asyncio.sleep(sleep_secs)
    print('All execution rounds executed successfully.')
