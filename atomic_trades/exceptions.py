class MarketDoesNotExistsError(Exception):
    pass


class InvalidConditionComparatorError(Exception):
    pass


class ConditionNotEvaluatedError(Exception):
    pass


class ConditionError(Exception):

    def __init__(self, message, failed_conditions):
        self.message = message
        self.failed_conditions = failed_conditions

    def __str__(self):
        return 'f{self.message}: {self.failed_conditions}'


class PreConditionError(ConditionError):

    def __init__(self, failed_conditions):
        message = "Commands were not executed because following pre conditions were not satisfied"
        super().__init__(message, failed_conditions)


class PostConditionError(ConditionError):

    def __init__(self, failed_conditions):
        message = "Commands were executed but following post conditions were not satisfied"
        super().__init__(message, failed_conditions)


class CommandExecutionError(Exception):

    def __init__(self, failed_commands_dict):
        self.message = "Commands were executed but following commands raised error during execution"
        self.failed_commands_dict = failed_commands_dict

    def __str__(self):
        return 'f{self.message}: {self.failed_commands_dict}'
