
import time
import pynput

import obj

key_down_funcs = list()
key_up_funcs   = list()
key_encode_literal = lambda event: obj.Value(content=[obj.Value(content=event.char, kind='char')], kind='string')
key_listener = pynput.keyboard.Listener(
    on_press    = lambda event: [x(key_encode_literal(event)) for x in key_down_funcs],
    on_release  = lambda event: [x(key_encode_literal(event)) for x in key_up_funcs],
)
key_listener.start()

mouse_click_funcs = list()
mouse_listener = pynput.mouse.Listener(
    on_click = lambda event: [
        x(obj.Value(content=None, kind='null')) 
        for x in mouse_click_funcs
    ]
)
mouse_listener.start()



class Builtin:
    ctx : obj.Ctx

    def addEventListener(event, func):
        metafunc = lambda param: func.content.call(Builtin.ctx, [param])
        match event.render():
            case 'keydown':    key_down_funcs.append(metafunc)
            case 'keyup'  :      key_up_funcs.append(metafunc)
            case 'click'  : mouse_click_funcs.append(metafunc)


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

    def one():      return obj.Value(content= 1, kind='int')
    def two():      return obj.Value(content= 2, kind='int')
    def three():    return obj.Value(content= 3, kind='int')
    def four():     return obj.Value(content= 4, kind='int')
    def five():     return obj.Value(content= 5, kind='int')
    def six():      return obj.Value(content= 6, kind='int')
    def seven():    return obj.Value(content= 7, kind='int')
    def eight():    return obj.Value(content= 8, kind='int')
    def nine():     return obj.Value(content= 9, kind='int')
    def ten():      return obj.Value(content=10, kind='int')

    def current(x): return x

    def next(x):
        old = x.content

        while old == x.content:
            #yup, it just spinlocks :3
            # hey! i never said that this was *good* implementation
            time.sleep(0.1)

        return x

setattr(Builtin, "await", lambda x: x)


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


