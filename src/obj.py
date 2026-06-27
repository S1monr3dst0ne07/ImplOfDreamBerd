
from dataclasses import dataclass as dc
from dataclasses import field
import dataclasses
import typing
import time
import datetime
import json
import copy
import redis

import error
from conf import Config
import tree



@dc
class Value:
    content : typing.Any
    kind : str

    editable   : bool = True
    assignable : bool = True

    # properties inherted on tree.AstDecl.run
    # these need to be stored here to make json pickeling possible
    lifetime : int | None = None
    lifetype : typing.Literal['default', 'stmt', 'sec', 'infty'] = 'default'

    stmt_alive : bool = True # local statement aliveness (updated by tree.AstBlock on schedule pass)
    time_born : int = -1 #unix timestamp of last variable conception

    previous : "Value" = None

    def __post_init__(self):
        self._check_deleted()

    def __hash__(self):
        match self.content:
            case list(): return hash(tuple(self.content))
            case x:      return hash(self.content)

    def flat(self):
        subvalues = [self]
        match self.kind:
            case 'string': subvalues += [x.flat() for x in self.content]
            case 'array' | 'dict': subvalues += [x.flat() for x in self.content.values()]

        return subvalues

    def _edit(self, ctx):
        if not self.editable:
            error.error(f'Attempting to edit uneditable value: `{self.render()}`')
        self._mut(ctx)

    def _assign(self, ctx):
        if not self.assignable:
            error.error(f'Attempting to assign unassignable value: `{self.render()}`')
        self._mut(ctx)

    def _pre_mut(self):
        self.previous = copy.deepcopy(self)

    def _mut(self, ctx):
        self._check_deleted()
        ctx.mutate(self)

        #`Date.now()` magic time value
        if self.kind == 'magictime':
            with open(Config.time_offset, 'w') as f:
                f.write(str(self.content))

    def _check_deleted(self):
        if self in tree.deleted_values:
            error.error(f"Value `{self.render()}` has been deleted.")

    def alive(self):
        match self.lifetype:
            case 'default': return True
            case 'infty': return True # for ever and infinity
            case 'stmt': return self.stmt_alive
            case 'sec' :
                passed = time.time() - self.time_born
                return passed < self.lifetime

            case x:
                error.internal(f"Unknown lifetype: `{x}`")


    def render(self):
        match self.kind:
            case 'string':
                return ''.join(x.render() for x in self.content)
            case 'char':
                return self.content
            case 'null': return "NULL"
            case 'undefined': return "undefined"
            case 'int' | 'float' | 'bool':
                return str(self.content)
            case 'array':
                indices = sorted(self.content.keys())
                seg = []

                for x in indices:
                    seg.append(self.content[x].render())
                    seg.append(', ')

                seg.pop()
                return f"[{''.join(seg)}]"

            case 'dict':
                return str({ k.render() : v.render() for k, v in self.content.items()})

            case 'metaclass':
                return "<metaclass object>"
            case 'class':
                rendered = { k : v.render() for k, v in self.content.items()}
                return f"<class {rendered}>"

            case 'magictime':
                return str(datetime.datetime.fromtimestamp(
                    time.time() + (self.content / 1000) # ms to float secs
                ))

            case x:
                error.error(f"Unable to render type: `{x}`")

    @classmethod
    def from_json(cls, json):
        match json['kind']:
            case 'null': content = None
            case 'string' | 'array':
                content = [cls.from_json(x) for x in json['content']]
            case 'int':   content = int(json['content'])
            case 'float': content = float(json['content'])
            case 'bool':  content = json['content'] == 'True'
            case 'char':  content = json['content']

        return cls(
            content, 
            kind=json['kind'], 
            editable=json['editable'] == 'True',
            assignable=json['assignable'] == 'True',
            lifetime=(int if json['lifetime'] != "None" else str)(json['lifetime']),
            lifetype=json['lifetype'],
            time_born=float(json['time_born'])
        )

    def to_json(self):
        match self.kind:
            case 'null': content = None
            case 'string' | 'array': 
                content = [x.to_json() for x in self.content]
            case 'int': content = str(self.content)
            case 'float': content = str(self.content)
            case 'bool': content = str(self.content)
            case 'char': content = self.content

        return {
            'content': content,
            'kind': self.kind,
            'editable': str(self.editable),
            'assignable': str(self.assignable),
            'lifetime': str(self.lifetime),
            'lifetype': self.lifetype,
            'time_born': str(self.time_born)
        }



@dc
class Scope:
    locals : dict[str, Value] = field(default_factory=lambda: {})
    when   : dict[str, list["tree.AstWhen"]] = field(default_factory=lambda: {})

    def find_local_name_by_value(self, value):
        for name, supervalue in self.locals.items():
            for subvalue in supervalue.flat():
                if subvalue is value:
                    return name

    def copy(self):
        new = Scope()
        # the values in scope must be shallow copies to allow
        # passing and editing contains in different scopes.
        new.locals = { k : copy.copy(v) for k, v in self.locals.items() }
        new.when   = self.when.copy()
        return new


    def __getitem__(self, index):
        return self.locals[index]
    def __setitem__(self, index, new):
        self.locals[index] = new
    def __contains__(self, elem):
        return elem in self.locals



@dc
class Ctx:
    scope : Scope = field(default_factory=lambda: Scope())
    stack : list = field(default_factory=lambda: [])

    eternal : dict[str, Value] = field(default_factory=lambda: {})

    redis = redis.Redis(
        host = Config.eternal_var_db,
        port = 6379,
        db = 0,
        decode_responses = True
    )

    def __post_init__(self):
        for key in self.redis.keys():
            self.eternal[key] = Value.from_json(
                json.loads(self.redis.get(key))
            )

    def eternal_upload(self, name):
        if self.redis.get(name) is not None:
            error.error(f"Unable to declare immutable `{name}` because it already exists.")

        value = self.scope[name]

        # update remote
        self.redis.set(name, json.dumps(
            self.scope[name].to_json()
        ))

        # update local cache
        self.eternal[name] = value

    def load(self):
        with open(Config.local_var_db, 'r') as f:
            for k, v in json.load(f).items():
                self.scope[k] = Value.from_json(v)

    def save(self):
        db = {}
        for k, v in self.scope.locals.items():
            #other variable types cannot persist, because that would require solving the halting problem. sorry TwT
            if v.lifetype in ('infty', 'sec'): 
                db[k] = v.to_json()


        with open(Config.local_var_db, 'w') as f:
            json.dump(db, f, indent=3) # wow, look, even the variable database file uses 3 space as indents.

    def mutate(self, value):
        self.when_trigger(value)

    def when_trigger(self, value):
        #lookup name of object in scope
        name = self.scope.find_local_name_by_value(value)

        if name in self.scope.when:
            for when in self.scope.when[name]:
                when.check(self)

    def push_scope(self):
        self.stack.append(self.scope.copy())

    def pop_scope(self):
        self.scope = self.stack.pop()

    def scheduler(self, continuation):
        return continuation()




