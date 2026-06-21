
from dataclasses import dataclass as dc
from dataclasses import field
import typing

import error


@dc
class Value:
    content : typing.Any
    kind : str

    editable   : bool = False
    assignable : bool = False

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

            case x:
                error.error(f"Unable to render type: `{x}`")

@dc
class Ctx:
    scope : dict[str, Value] = field(default_factory=lambda: {})




