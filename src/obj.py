
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
            error.error(f'Attempting to edit uneditable value: `{self}`')

    def _assign(self):
        if not self.assignable:
            error.error(f'Attempting to assign unassignable value: `{self}`')


@dc
class Ctx:
    scope : dict[str, Value] = field(default_factory=lambda: {})




