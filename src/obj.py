
from dataclasses import dataclass as dc
from dataclasses import field
import typing


@dc
class Value:
    content : typing.Any
    kind : str

@dc
class Variable:
    value : Value
    editable   : bool = False
    assignable : bool = False

@dc
class Ctx:
    scope : dict[str, Variable] = field(default_factory=lambda: {})




