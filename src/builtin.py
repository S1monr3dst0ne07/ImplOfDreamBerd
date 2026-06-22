
import obj

class Builtin:
    ctx : obj.Ctx

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
        elem = value.content.pop(0)
        value._edit()
        return elem

    def push(value, new):
        value.content.append(new)
        value._edit()
        return Builtin._null()

    def true():
        return obj.Value(content=True, kind='bool')
    def false():
        return obj.Value(content=False, kind='bool')


def get_all():
    builtins = {}

    for name in dir(Builtin):
        method = getattr(Builtin, name)
        if name.startswith('_'): continue
        if not callable(method): continue

        builtins[name] = method
        
    return builtins

def inject(ctx):
    Builtin.ctx = ctx
    for name, func in get_all().items():
        ctx.scope[name] = obj.Value(
            content = func,
            kind = 'metafunc',
            editable = False,
            assignable = False,
        )


    ctx.scope['True'] = ctx.scope['true']
    ctx.scope['False'] = ctx.scope['false']


