
import typing
from dataclasses import dataclass as dc

import error


@dc
class AstLeaf:
    value : typing.Any

    @staticmethod
    def _compute_quote_size(token):
        size = 0
        for char in token.content:
            if char == "'": size += 1
            if char == '"': size += 2

        return size

    @classmethod
    def _parse_string(cls, stream):
        token = stream.popt()
        size = cls._compute_quote_size(token)

        string_segments = []
        while cls._compute_quote_size(stream.peekt()) != size:
            string_segments.append(stream.pop()) 
        stream.pop() #discard closing quote

        return "".join(string_segments)

    @classmethod
    def parse(cls, stream):
        stream.space()
        match stream.peekt().kind:
            case 'quote': leaf = cls._parse_string(stream)
        stream.space()
        return cls(leaf)

    def eval(self):
        return self.value
        

@dc
class AstCall:
    name : str
    params : list[AstLeaf]

    @classmethod
    def parse(cls, stream):
        name = stream.pop()
        params = []

        while stream.peekt().kind not in ('eos', 'debug'):
            params.append(AstLeaf.parse(stream))
            if stream.peek() != ',': break
            stream.pop()

        return cls(name, params)

    def run(self):
        params = [x.eval() for x in self.params]

        funcs = {
            'print': lambda x: (print(x), "<print function>")[1],
        }

        return funcs[self.name](*params)


@dc
class AstStmt:
    sub : typing.Any
    eos : str

    @classmethod
    def parse(cls, stream):
        match stream.peek():
            case x: sub = AstCall.parse(stream)

        token = stream.popt()
        if token.kind not in ('eos', 'debug'):
            error.token(token, "End of line is not `!` or `?`.")

        return cls(sub, token.content)

    def run(self):
        res = self.sub.run()
        
        match self.eos:
            case "?": print(f"[DEBUG] {res}")

@dc
class AstProg:
    content : list[AstStmt]

    
    @classmethod
    def parse(cls, stream):
        content = []
        while stream.has():
            content.append(AstStmt.parse(stream))

        return cls(content)

    def run(self):
        for stmt in self.content:
            stmt.run()

            



