
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

    def peekt(self):
        return self.stream[0]

    def popt(self):
        return self.stream.pop(0)

    def peek(self):
        return self.peekt().content

    def pop(self):
        return self.popt().content

    def has(self):
        return len(self.stream) > 0

    #DB has significant whitespace which means it cannot be
    # discarded by the lexer. Streamer.space skips whitespace
    # in circumstances where it doesn't matter
    def space(self):
        if self.peekt().kind == "space":
            self.pop()
        


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
