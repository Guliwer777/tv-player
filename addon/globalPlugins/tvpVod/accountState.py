"""Read local pairing state without contacting providers or revealing credentials."""
from importlib import import_module


def connected(provider):
    module=import_module('.'+{'tvp':'tvp','canal':'canal','polsat':'polsat','playerpl':'playerpl'}[provider]+'_account',__package__)
    try:return bool(module.load())
    except (OSError,ValueError,TypeError,module.AccountError):return False
