from functools import wraps
from inspect import signature, _empty

def auto_set_fields(f):
    f_sig = signature(f)

    @wraps(f)
    def wrapper(*args, **kwargs):
        caller_specified_fields = dict(f_sig.bind(*args, **kwargs).arguments)
        self = caller_specified_fields.pop('self')

        f_defaults = {k: v.default for k, v in \
                       signature(f).parameters.items() \
                       if not v.default is _empty}

        f_defaults.update(caller_specified_fields)
        # Set default values
        for k, v in f_defaults.items():
            setattr(self, k, v)

        return f(*args, **kwargs)

    return wrapper


def fst(tup):
    return(tup[0])


def snd(tup):
    return(tup[1])


def swap(tup):
    x, y = tup
    return y, x


def f_apply(f,x):
    return f(x)


def assert_len(l, xs):
    # TODO: custom exception classes
    assert len(xs) == l, "List did not have the expected number of items!"
    return xs


def compose(f,g):
    return lambda x: f(g(x))


def intercalate(x, ys):
    '''Like join, but filters Falsey values'''
    return x.join([x for x in ys if x])


class add_methods(object):
    """Add the public attributes of a mixin to another class.
    Attribute name collisions result in a TypeError if force is False.
    If a mixin is an ABC, the decorated class is registered to it,
    indicating that the class implements the mixin's interface.
    """
    @auto_set_fields
    def __init__(self, *attrs):
        pass

    def __call__(self, cls):
        for attr in self.attrs:
            if hasattr(cls, attr.__name__):
                raise TypeError("name collision ({})".format(attr.__name__))
            else:
                setattr(cls, attr.__name__, attr)

        return cls


class add_method_as(object):
    """Add the public attributes of a mixin to another class.
    Attribute name collisions result in a TypeError if force is False.
    If a mixin is an ABC, the decorated class is registered to it,
    indicating that the class implements the mixin's interface.
    """
    @auto_set_fields
    def __init__(self, attr, as_name):
        pass

    def __call__(self, cls):
        if hasattr(cls, self.as_name):
            print(dir(cls))
            raise TypeError("name collision ({})".format(self.as_name))
        else:
            setattr(cls, self.as_name, self.attr)

        return cls


def filter_split(f, l):
    accepted = []
    rejected = []
    [accepted.append(x) if f(x) else rejected.append(x) for x in l]
    return (accepted, rejected)



if __name__ == '__main__':
    print(filter_split(lambda x:x<5, range(10)))
