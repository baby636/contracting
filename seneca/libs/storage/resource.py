from seneca.engine.interpret.utils import ItemNotFoundException
from seneca.libs.storage.datatype import DataType
from seneca.libs.storage.datatype import DELIMITER


class ResourceObj:

    instance = None

    def __set__(self, instance, value):
        k, v = instance.resource, value
        hash_key = instance.key.rsplit(DELIMITER, 1)[0]
        instance.driver.hset(hash_key, k, instance.encode(v))

    def __get__(self, instance, parent):
        hash_key = instance.key.rsplit(DELIMITER, 1)[0]
        res = instance.driver.hget(hash_key, instance.resource)
        if not res:
            raise ItemNotFoundException('Cannot find {} in {}'.format(instance.resource, instance.__repr__()))
        return instance.decode(res)


class Resource(DataType):
    resource_obj = ResourceObj()
