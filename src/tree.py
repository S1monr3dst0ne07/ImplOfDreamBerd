
import typing
from dataclasses import dataclass as dc

import error
import sym
import obj
import builtin




# function calls and Variable accesses cannot be differentiated at parse-time.
# hence they both are unified under the AstScopeAccess node type.
# `iden` and `subj` cannot be expression here because it makes it impossible to parse.
# you can't know, for example, how to parse the following if you assume function references can be expression:
# ` 1 + a 1, 2, 3`
# is it `(1 + a)(1, 2, 3)` or `1 + a(1, 2, 3)`?
# hence this implement assumes function references cannot be expressions.
# it would parse the upper expression as such:
# `1 + a(1, 2, 3)`

@dc
class AstScopeAccess:
    iden : str #variable / function name
    subj : str | None # optional subject prefix
    params : list[typing.Any]

    @classmethod
    def parse(cls, stream):
        iden = stream.pop()
        params = []

        # syntax sugar for `subj.verb(obj...)` => `verb(subj, obj...)`
        subj = None
        if stream.peek() == '.':
            stream.expect('.')
            subj, iden = iden, stream.pop()

        while stream.peekt().kind not in ('eos', 'debug'):
            params.append(AstExpr.parse(stream))
            if stream.peek() != ',': break
            stream.expect(',')

        return cls(iden, subj, params)

    def _var_lookup(self, ctx, iden):
        if iden not in ctx.scope:
            error.error(f"Identifier `{iden}` does not exist in scope.")
        return ctx.scope[iden]

    def run(self, ctx):
        params = (
            [self._var_lookup(ctx, self.subj)] if self.subj else [] + 
            [x.eval(ctx) for x in self.params]
        )
        value = self._var_lookup(ctx, self.iden)

        if value.kind == 'metafunc':
            # calls as function if type if iden in scope is metafunc
            return value.content(*params)

        #otherwise it has to have been a variable access
        return value




@dc
class AstLeaf:
    value : obj.Value

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
            case 'numb':  
                leaf = int(stream.pop())
                if stream.peekt().kind == 'dot':
                    stream.pop()
                    leaf += float(f"0.{stream.pop()}")
                value = obj.Value(leaf, kind='numb')

            case 'quote': 
                value = obj.Value(
                    content = [obj.Value(
                        content = x,
                        kind = 'char',
                        editable = True,
                        assignable = True,
                    ) for x in 
                    cls._parse_string(stream)],
                    kind = 'string',
                )
            case 'iden' | 'sym': 
                value = AstScopeAccess.parse(stream)

            case x: error.error(f"Unknown leaf kind: {stream.popt()}")

        stream.space()
        return cls(value)

    def eval(self, ctx):
        if type(self.value) is AstScopeAccess:
            return self.value.run(ctx)

        if self.value.kind == 'numb' and self.value.content in ctx.literal_numb_mapper:
            return obj.Value(content=ctx.literal_numb_mapper[self.value.content], kind='numb')

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

    def eval(self, ctx):
        sub = self.sub.eval(ctx)
        value = sub.content

        match self.op:
            case ';': res = not value

        return obj.Value(content=res, kind=sub.kind)



@dc
class AstExpr:
    space : int 
        # how much whitespace surround the operators? 
        # used for graph rewriting

    op : str
    left  : "AstExpr | AstUn | AstLeaf"
    right : "AstExpr | AstUn | AstLeaf"

    @classmethod
    def parse(cls, stream, no_func_calls=False):
        #! TODO: implement no_func_calls 

        left = AstUn.parse(stream)
        left_space = stream.space()

        if stream.peek() not in sym.op:
            return left

        op = stream.pop()
        right_space = stream.space()
        right = AstExpr.parse(stream)

        return cls(
            max(left_space, right_space),
            left = left,
            right = right,
            op = op
        )

    def eval(self, ctx):
        left  = self.left.eval(ctx)
        right = self.right.eval(ctx)

        if right.kind != left.kind:
            error.error("Cannot operator with `{self.op}` on `{left}` and `{right}` because their types do not match.")

        l = left.content
        r = right.content
        match self.op:
            case '+': res = l + r
            case '-': res = l - r
            case '*': res = l * r
            case '/': res = l / r

        return obj.Value(content=res, kind=left.kind)






@dc
class AstIf:
    cond : AstExpr
    body : "AstStmt"

    @classmethod
    def parse(cls, stream):
        stream.expect('if')
        cond = AstExpr.parse(stream)
        body = AstStmt.parse(stream)
        return cls(cond, body)

    def run(self, ctx):
        if self.cond.eval():
            self.body.run(ctx)


@dc
class AstBlock:
    stmts : list["AstStmt"]

    class BlockClose: pass

    @classmethod
    def parse(cls, stream):
        stream.expect('{')

        stmts = []
        while True:
            sub = AstStmt.parse(stream)
            if sub == cls.BlockClose: break
            stmts.append(sub)

        stream.expect('}')
        return cls(stmts)

    def run(self, ctx):
        for stmt in self.stmts:
            stmt.run(ctx)


@dc
class AstDecl:
    editable   : bool
    assignable : bool
    name : str
    expr : AstExpr

    @classmethod
    def parse(cls, stream):
        assignable = {'const' : False, 'var' : True}[stream.pop()]
        if stream.peek() not in ('const', 'var'):
            error.token(stream.pop(), "`const` / `var` not followed by `const` / `var`.")
        editable = {'const' : False, 'var' : True}[stream.pop()]

        name = stream.pop()

        if stream.peek() != '=':
            error.token(stream.pop(), "Expected `=`.")
        stream.pop()

        expr = AstExpr.parse(stream)

        return cls(editable, assignable, name, expr)

    def run(self, ctx):
        if self.name in ctx.scope:
            error.error(f"Variable `{self.name}` already declared.")

        init = self.expr.eval(ctx)

        init.editable = self.editable
        init.assignable = self.assignable

        ctx.scope[self.name] = init


@dc
class AstAssign:
    dst : typing.Any
    src : typing.Any

    @classmethod
    def parse(cls, stream):
        dst = AstExpr.parse(
            stream, 
            no_func_calls=True #makes it possible to parse signals
        )
        stream.expect('=')
        src = AstExpr.parse(stream)

        return cls(dst, src)

    def run(self, ctx):
        dst = self.dst.eval(ctx)
        src = self.src.eval(ctx)
        dst._assign()

        dst.content = src.content
        dst.kind    = src.kind

@dc
class AstStmt:
    sub : typing.Any
    eos : str

    @classmethod
    def parse(cls, stream):
        #TODO: indent detection
        stream.space()

        need_eos = True
        first, second = stream.lookhead(2)
        match first.content, second.content:
            case '}', _: return AstBlock.BlockClose
            case '{', _:  #}
                sub = AstBlock.parse(stream)
                need_eos = False
            case 'if', _: 
                sub = AstIf.parse(stream)
                need_eos = False

            case _, '=':
                sub = AstAssign.parse(stream)

            case x, y if all(i in ('const', 'var') for i in (x, y)):
                sub = AstDecl.parse(stream)

            case x: 
                sub = AstScopeAccess.parse(stream)




        eos = None
        if need_eos:
            token = stream.popt()
            eos = token.content
            if token.kind not in ('eos', 'debug'):
                error.token(token, "End of line is not `!` or `?`.")

        stream.space()
        return cls(sub, eos)

    def run(self, ctx):
        res = self.sub.run(ctx)
        
        match self.eos:
            case "?": print(f"[DEBUG] {res.render()}")

@dc
class AstProg:
    content : list[AstStmt]

    
    @classmethod
    def parse(cls, stream):
        content = []
        while stream.has():
            content.append(AstStmt.parse(stream))

        return cls(content)

    def run(self, ctx):
        builtin.inject(ctx)

        for stmt in self.content:
            stmt.run(ctx)

            



