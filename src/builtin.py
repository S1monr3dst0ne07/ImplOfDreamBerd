
import obj

class Builtin:
    def print(value):
        print(value.render())
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
        return value.content.pop(0)

    def push(value, new):
        value._edit()
        value.content.append(new)
        return Builtin._null()


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

