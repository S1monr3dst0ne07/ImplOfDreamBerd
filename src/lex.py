
from dataclasses import dataclass as dc


def get_kind(char):
    match char:
        case '"': return 'quote'
        case "'": return 'quote'
        case '!': return 'eos'
        case '?': return 'debug'
        case ' ': return 'space'
        case '{': return 'blockopen'
        case '}': return 'blockclose'
        case '.': return 'dot'
        case '\n': return 'newline'
        case x if x.isdigit(): return 'numb'
        case x if x.isalpha(): return 'iden'
        case _: return 'sym'


@dc
class Token:
    content : str
    kind : str

@dc
class Streamer:
    stream : list[Token]
    ignore_space : bool = True

    def _check(self):
        if self.ignore_space and self.stream[0].kind == "space":
            self.stream.pop(0)

    def peekt(self):
        self._check()
        return self.stream[0]

    def popt(self):
        self._check()
        return self.stream.pop(0)

    def peek(self):
        return self.peekt().content

    def pop(self):
        return self.popt().content

    def has(self):
        return len(self.stream) > 0

    def _wrap(self):
        if self.peekt().kind == 'newline':
            self.pop()

    #DB has significant whitespace which means it cannot be
    # discarded by the lexer. Streamer.space skips whitespace
    # in circumstances where it doesn't matter
    def space(self):
        if not self.has():
            return 0

        self._wrap()

        if self.peekt().kind == "space":
            return len(self.pop())

        self._wrap()

        return 0
        

    def expect(self, should):
        tok = self.popt()
        if tok.content != should:
            error.token(tok, f"Expected `{should}` but go `{tok.content}`.")


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
