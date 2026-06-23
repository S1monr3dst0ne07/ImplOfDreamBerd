
import time
from pynput import keyboard

import obj

key_down_funcs = list()
key_up_funcs   = list()
key_encode_literal = lambda event: obj.Value(content=event.char, kind='char')
key_listener = keyboard.Listener(
    on_press    = lambda event: [x(key_encode_literal(event)) for x in key_down_funcs],
    on_release  = lambda event: [x(key_encode_literal(event)) for x in key_up_funcs],
)
key_listener.start()



class Builtin:
    ctx : obj.Ctx

    def addEventListener(event, func):
        metafunc = lambda char: func.content.call(Builtin.ctx, [char])
        match event.render():
            case 'keydown': key_down_funcs.append(metafunc)
            case 'keyup'  :   key_up_funcs.append(metafunc)


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

    def sleep(secs):
        time.sleep(1)

    def undefined():
        return obj.Value(content=None, kind='undefined')
    def maybe():
        return obj.Value(content='maybe', kind='bool')


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


