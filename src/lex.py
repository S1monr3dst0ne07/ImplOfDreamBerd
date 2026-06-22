
from dataclasses import dataclass as dc
import regex

import error


def get_kind(char):
    match char:
        case '\0': return 'meta flush'
        case '"': return 'quote'
        case "'": return 'quote'
        case '!': return 'eos'
        case '?': return 'debug'
        case ' ': return 'space'
        case '{': return 'blockopen'
        case '}': return 'blockclose'
        case '[': return 'arrayopen'
        case ']': return 'arrayclose'
        case '.': return 'dot'
        case '\n': return 'newline'
        case x if x.isdigit(): return 'numb'
        case x if x.isalpha(): return 'iden'
        case _: return 'sym'


@dc
class Token:
    content : str
    kind : str

    line : int

@dc
class Streamer:
    stream : list[Token]

    def _check(self):
        if self.stream == []: return
        if self.stream[0].kind == "space":
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
        self._check()
        return len(self.stream) > 0

    #DB has significant whitespace which means it cannot be
    # discarded by the lexer. Streamer.space skips whitespace
    # in circumstances where it doesn't matter
    def space(self):
        if self.has() and self.peekt().kind == "space":
            return len(self.pop())

        return 0
        

    def expect(self, should):
        tok = self.popt()
        if tok.content != should:
            error.token(tok, f"Expected `{should}` but go `{tok.content}`.")

    def lookhead(self, count):
        stream = self.stream.copy()
        toks = [self.popt() if self.has() else Token('', '', 0) for _ in range(count)]
        self.stream = stream
        return toks


def tokenize(path):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()

    "They get replaced with whitespace."
    src = src.replace('(', ' ').replace(')', ' ')

    #cluster unicode graphemes
    graphemes = regex.findall(r"\X", src)

    stream = []
    buffer = ""
    line = 1

    state = None
    comment = False
    for char in graphemes + ['\0']:
        kind = get_kind(char)

        if buffer == '//': comment = True

        if kind != state and state and not comment:
            if state != 'newline':
                stream.append(Token(
                    buffer, state, line
                ))
            buffer = ""

        if char == '\n': 
            comment = False
            buffer = ""

        state = kind
        buffer += char

        if char == '\n':
            line += 1

    return Streamer(stream)
