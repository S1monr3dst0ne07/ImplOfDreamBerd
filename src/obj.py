
import typing
from dataclasses import dataclass as dc

import error
import sym


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
            case 'numb':  leaf = int(stream.pop())
            case 'quote': leaf = cls._parse_string(stream)
            case 'iden':
                match stream.pop():
                    case 'false': leaf = False
            case x: error.error(f"Unknown leaf kind: {stream.popt()}")
        stream.space()
        return cls(leaf)

    def eval(self):
        return self.value


@dc
class AstUn:
    op : str
    sub : AstLeaf

    @classmethod
    def parse(cls, stream):
        if stream.peek() not in sym.un_op:
            return AstLeaf.parse(stream)

        op = stream.pop()
        stream.space() #the spec makes no mention of unary operator separation 
        sub = AstLeaf.parse(stream)
        return cls(op, sub)


@dc
class AstExpr:
    space : int 
        # how much whitespace surround the operators? 
        # used for graph rewriting

    op : str
    left  : "AstExpr | AstUn | AstLeaf"
    right : "AstExpr | AstUn | AstLeaf"

    @classmethod
    def parse(cls, stream):
        left = AstUn.parse(stream)
        left_space = stream.space()

        if stream.peek() not in sym.op:
            return left

        op = stream.pop()
        right_space = stream.space()
        right = AstUn.parse(stream)
        return cls(
            max(left_space, right_space),
            left = left,
            right = right,
            op = op
        )

    def eval(self):
        left  = self.left.eval()
        right = self.left.eval()

        match self.op:
            case '+': res = left + right
            case '-': res = left - right
            case '*': res = left * right
            case '/': res = left / right

        return res




@dc
class AstCall:
    name : str
    params : list[typing.Any]

    @classmethod
    def parse(cls, stream):
        name = stream.pop()
        params = []

        while stream.peekt().kind not in ('eos', 'debug'):
            params.append(AstExpr.parse(stream))
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
class AstIf:
    cond : AstExpr
    body : "AstStmt"

    @classmethod
    def parse(cls, stream):
        stream.pop()
        stream.space()
        cond = AstExpr.parse(stream)
        stream.space()
        body = AstStmt.parse(stream)
        return cls(cond, body)


@dc
class AstBlock:
    stmts : list["AstStmt"]

    class BlockClose: pass

    @classmethod
    def parse(cls, stream):
        stream.pop()

        stmts = []
        while True:
            sub = AstStmt.parse(stream)
            if sub == cls.BlockClose: break
            stmts.append(sub)

        stream.pop()
        return cls(stmts)


@dc
class AstStmt:
    sub : typing.Any
    eos : str

    @classmethod
    def parse(cls, stream):
        #TODO: indent detection
        stream.space()

        need_eos = True
        tmp = stream.peek()
        match tmp:
            case '}': return AstBlock.BlockClose
            case '{': 
                sub = AstBlock.parse(stream)
                need_eos = False
            case 'if': 
                sub = AstIf.parse(stream)
                need_eos = False
            case x: sub = AstCall.parse(stream)

        eos = None
        if need_eos:
            token = stream.popt()
            eos = token.content
            if token.kind not in ('eos', 'debug'):
                error.token(token, "End of line is not `!` or `?`.")

        stream.space()
        return cls(sub, eos)

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

            



