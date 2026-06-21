
import obj

class Builtin:
    def print(value):
        print(value.content)
        return "<print>"

    def _null():
        return obj.Value(
            content=None,
            kind='null',
            editable = False,
            assignable = True,
        )

    def pop(value):
        value._edit()
        
        res = Builtin._null()
        match value.kind:
            case 'string':
                res, *tail = value.content
                value.content = "".join(tail)

        return res


def get_all():
    builtins = {}

    for name in dir(Builtin):
        method = getattr(Builtin, name)
        if name.startswith('_'): continue
        if not callable(method): continue

        builtins[name] = method
        
    return builtins

def inject(ctx):
    for name, func in get_all().items():
        ctx.scope[name] = obj.Value(
            content = func,
            kind = 'metafunc',
            editable = False,
            assignable = False,
        )

