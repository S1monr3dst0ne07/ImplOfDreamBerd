
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

    def _edit(self):
        if not self.editable:
            error.error(f'Attempting to edit uneditable value: `{self.render()}`')

    def _assign(self):
        if not self.assignable:
            error.error(f'Attempting to assign unassignable value: `{self.render()}`')

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
    when   : list["tree.AstWhen"] = field(default_factory=lambda: [])

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

    when_level : int = 0

    def push_scope(self):
        self.stack.append(dataclasses.replace(self.scope))

    def pop_scope(self):
        self.scope = self.stack.pop()

    def scheduler(self, continuation):
        
        self.when_level += 1
        if self.when_level == 1:
            for when in self.scope.when:
                when.check(self)
        self.when_level -= 1

        continuation()



