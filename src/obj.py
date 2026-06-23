
from dataclasses import dataclass as dc
from dataclasses import field
import dataclasses
import typing

import error



@dc
class Value:
    content : typing.Any
    kind : str

    editable   : bool = True
    assignable : bool = True

    stmt_alive : bool = True # local statement aliveness (updated by tree.AstBlock on schedule pass)
    time_born : int = -1 #unix timestamp of last variable conception
    time_parent : "tree.AstDecl" = None #who gave birth to variable

    def _edit(self, ctx):
        if not self.editable:
            error.error(f'Attempting to edit uneditable value: `{self.render()}`')
        self._mut(ctx)

    def _assign(self, ctx):
        if not self.assignable:
            error.error(f'Attempting to assign unassignable value: `{self.render()}`')
        self._mut(ctx)

    def _mut(self, ctx):
        ctx.mutate(self)

    def alive(self):
        if self.stmt_alive: return True

        return False

    def render(self):
            
        match self.kind:
            case 'string':
                return ''.join(x.render() for x in self.content)
            case 'char':
                return self.content
            case 'null':
                return "NULL"
            case 'numb' | 'bool':
                return str(self.content)
            case 'array':
                indices = sorted(self.content.keys())
                seg = []

                for x in indices:
                    seg.append(self.content[x].render())
                    seg.append(', ')

                seg.pop()
                return f"[{''.join(seg)}]"

            case x:
                error.error(f"Unable to render type: `{x}`")

@dc
class Scope:
    locals : dict[str, Value] = field(default_factory=lambda: {})
    when   : dict[str, list["tree.AstWhen"]] = field(default_factory=lambda: {})

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

    def mutate(self, value):
        #lookup name of object in scope
        name = next(k for k,v in self.scope.locals.items() if v == value)

        #process when triggers
        for when in self.scope.when[name]:
            when.check(self)

    def push_scope(self):
        self.stack.append(dataclasses.replace(self.scope))

    def pop_scope(self):
        self.scope = self.stack.pop()

    def scheduler(self, continuation):
        continuation()



