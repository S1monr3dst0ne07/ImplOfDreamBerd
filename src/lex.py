
from dataclasses import dataclass as dc


def get_kind(char):
    match char:
        case '"': return 'quote'
        case "'": return 'quote'
        case '!': return 'eos'
        case '?': return 'debug'
        case ' ': return 'space'
        case _: return 'sym'


@dc
class Token:
    content : str
    kind : str

@dc
class Streamer:
    stream : list[Token]


def tokenize(path):
    with open(path, 'r') as f:
        src = f.read()

    "They get replaced with whitespace."
    src = src.replace('(', ' ').replace(')', ' ')

    stream = []
    buffer = ""

    state = None
    for char in src:
        kind = get_kind(char)

        if kind != state and state:
            stream.append(Token(
                buffer, state
            ))
            buffer = ""

        state = kind
        buffer += char

    return Streamer(stream)
