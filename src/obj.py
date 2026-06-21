
from dataclasses import dataclass as dc
from dataclasses import field
import typing


@dc
class Value:
    content : typing.Any
    editable   : bool
    assingable : bool




@dc
class Ctx:
    scope : dict[str, Value] = field(default_factory=lambda: {})




