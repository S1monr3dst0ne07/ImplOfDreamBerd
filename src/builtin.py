
import obj

class Builtin:
    def print(value):
        print(value.content)
        return "<print>"


    def pop(value):
        print(value)



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

