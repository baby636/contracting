from ...execution.runtime import rt
from ...db.driver import ContractDriver


def export(fn):
    def ret_fn(*args, **kwargs):
        driver = rt.env.get('__Driver') or ContractDriver()
        owner = driver.hget(rt.ctx, driver.owner_key)
        if owner is None or owner == rt.ctx[-1]:
            return fn(*args, **kwargs)
        else:
            raise Exception('Caller is not the owner.')

    return ret_fn


exports = {
    '__export': export
}
