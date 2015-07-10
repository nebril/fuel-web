import abc


class ValidationError(Exception):
    pass


class BaseValidator(object):

    @abc.abstractmethod
    def validate(self, *args, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        self.validate(*args, **kwargs)


class HumanFormatSchemeValidator(BaseValidator):

    def validate(self, dict_scheme):
        pass


class PartitionSchemeValidator(BaseValidator):

    def validate(self, partition_scheme):
        pass
