
import typing
import time
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

        if stream.peek().isdigit() or stream.peekt().content not in (sym.op + sym.un_op + sym.block):
            # this check is needed to prevent `x + 5` from
            # being parsed as `x(+) 5`

            while stream.peekt().kind not in ('eos', 'debug'):
                params.append(AstExpr.parse(stream))
                if stream.peek() != ',': break
                stream.expect(',')

        return cls(iden, subj, params)

    def _var_lookup(self, ctx, iden):
        if iden not in ctx.scope:
            error.error(f"Identifier `{iden}` does not exist in scope.")
    
        var = ctx.scope[iden]
        if not var.alive():
            error.error(f"Trying to access variable `{iden}` but it's dead :(")
    
        return ctx.scope[iden]

    def run(self, ctx, lvalue=False):
        params = (
            [self._var_lookup(ctx, self.subj)] if self.subj else [] + 
            [x.run(ctx) for x in self.params]
        )
        value = self._var_lookup(ctx, self.iden)

        if value.kind == 'metafunc':
            # calls as function if type if iden in scope is metafunc
            return value.content(*params)

        if value.kind == 'func':
            return value.content.call(ctx, params)

        #otherwise it has to have been a variable access
        return value

    def vars(self):
        return [self.iden] + [x.vars() for x in self.params]



@dc
class AstLitArray:
    elems : list["AstExpr"]

    @classmethod
    def parse(cls, stream):
        stream.expect('[') #]
        elems = []

        while stream.peek() != ']':
            elems.append(AstExpr.parse(stream))
            if stream.peek() == ',':
                stream.expect(',')
        stream.expect(']')

        return cls(elems)

    def run(self, ctx):
        return obj.Value(
            content = { i : x.run(ctx) for i, x in enumerate(self.elems) },
            kind = 'array',
        )

@dc
class AstIndexAccess:
    name : str
    index : "AstExpr"

    @classmethod
    def parse(cls, stream):
        name = stream.pop()
        stream.expect('[') #]
        index = AstExpr.parse(stream)
        stream.expect(']')

        return cls(name, index)

    def run(self, ctx, lvalue=False):
        value = ctx.scope[self.name]
        index = self.index.run(ctx).content

        match value.kind:
            case 'array':
                index += 1
                if lvalue and index not in value.content:
                    value.content[index] = obj.Value(None, 'null')
                return value.content[index]
        



@dc
class AstLeaf:
    value : obj.Value

    def infer(self): pass

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
            string_segments.append(" " * stream.space())
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
                
            case 'arrayopen':
                value = AstLitArray.parse(stream)

            case 'iden' | 'sym': 
                if stream.lookhead(2)[1].kind == 'arrayopen':
                    value = AstIndexAccess.parse(stream)
                else:
                    value = AstScopeAccess.parse(stream)

            case x: error.error(f"Unknown leaf kind: {stream.popt()}")

        stream.space()
        return cls(value)

    def run(self, ctx):
        if type(self.value) in (AstScopeAccess, AstLitArray, AstIndexAccess):
            return self.value.run(ctx)

        #renamed literal number
        numb_name = str(self.value.content)
        if self.value.kind == 'numb' and numb_name in ctx.scope:
            return ctx.scope[numb_name]

        return self.value

    def vars(self):
        if type(self.value) is obj.Value:
            return []

        return self.value.vars()


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

    def run(self, ctx):
        sub = self.sub.run(ctx)
        value = sub.content

        match self.op:
            case ';': res = not value
            case '-': res = -value

        return obj.Value(content=res, kind=sub.kind)

    def vars(self):
        return self.sub.vars()



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
        right = AstExpr.parse(stream)

        return cls(
            max(left_space, right_space),
            left = left,
            right = right,
            op = op
        )

    def run(self, ctx):
        left  = self.left.run(ctx)
        right = self.right.run(ctx)

        if right.kind != left.kind:
            error.error(f"Cannot operator with `{self.op}` on `{left.render()}` and `{right.render()}` because their types do not match.")

        l = left.content
        r = right.content
        match self.op:
            case '+': res = l + r
            case '-': res = l - r
            case '*': res = l * r
            case '/': res = l / r
            case '==': res = l == r
            case ';=': res = l != r
            case '<': res = l < r
            case '>': res = l > r

            case x: print(f"UNIMPLEMENTED OP: {x}")

        return obj.Value(content=res, kind=left.kind)

    def vars(self):
        return self.left.vars() + self.right.vars()





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
        if self.cond.run(ctx).content:
            self.body.run(ctx)

@dc
class AstWhen:
    cond : AstExpr
    body : "AstStmt"

    def infer(self):
        self.body.infer()

    @classmethod
    def parse(cls, stream):
        stream.expect('when')
        cond = AstExpr.parse(stream)
        body = AstStmt.parse(stream)
        return cls(cond, body)

    def run(self, ctx):
        for dep in self.cond.vars():
            if dep not in ctx.scope.when:
                ctx.scope.when[dep] = []

            ctx.scope.when[dep].append(self)

    def check(self, ctx):
        if self.cond.run(ctx).content:
            self.body.run(ctx)


@dc
class AstBlock:
    stmts : list["AstStmt"]

    stmt_alive : list[set] #which vars alive during statement
    stmt_dead  : list[set] #"-" dead "-"

    #declaration have to be executed as soon as their lifetime starts 
    decl_init  : dict[str, "AstDecl"]

    class BlockClose: pass

    @classmethod
    def parse(cls, stream, prog=False):
        if not prog: stream.expect('{') #}

        stmts = []
        while stream.has():
            sub = AstStmt.parse(stream)
            if sub == cls.BlockClose: break
            stmts.append(sub)

        if not prog: stream.expect('}')
        return cls(stmts, [], [], {})

    def infer(self):
        self.stmt_alive = [set() for _ in self.stmts]
        relevent_stmts = [
            stmt for stmt in self.stmts 
            if type(stmt.sub) is AstDecl and
            stmt.sub.lifetime is not None and
            stmt.sub.lifetype == 'stmt'
        ]

        for stmt in relevent_stmts:
            decl = stmt.sub
            self.decl_init[decl.name] = decl

        #compute which variables are alive during each statement
        for index, stmt in enumerate(self.stmts):
            if stmt not in relevent_stmts: continue
            decl = stmt.sub

            timetravel = decl.lifetime < 0
            offset = (-1 if timetravel else 0)
            for _ in range(abs(decl.lifetime)):
                self.stmt_alive[index + offset].add(decl.name)
                offset += (-1 if timetravel else 1)

        #compute compliment (insert deep quote about yin and yang or smth)
        for index, stmt in enumerate(self.stmts):
            self.stmt_dead.append(set(
                varname for varname in [x.sub.name for x in relevent_stmts]
                if varname not in self.stmt_alive[index]
            ))

        #infer recursive
        for stmt in self.stmts:
            stmt.infer()

    def run(self, ctx, offset=1, index=0):
        #update variable livenesses
        def update(name, state):
            if name not in ctx.scope:
                #make sure alive variables are present in scope.
                #this is the actual time travel part right here lol,
                #we're executing a statement before it should actual run.
                if state: self.decl_init[name].run(ctx)
                else: return

            ctx.scope[name].stmt_alive = state

        for name in self.stmt_alive[index]: update(name, True)
        for name in self.stmt_dead [index]: update(name, False)

        #actual statment execution
        res = self.stmts[index].run(ctx)
        step = index + offset

        #scheduler base case
        if len(self.stmts) == step:
            return ctx.scheduler(lambda: res)

        #pass continuation into context scheduler.
        # this is some fucking haskell level programming right here.
        return ctx.scheduler(lambda: self.run(ctx, offset, step))




@dc
class AstDecl:
    editable   : bool
    assignable : bool
    name : str
    expr : AstExpr

    lifetime : int | None
    lifetype : typing.Literal['stmt', 'sec'] 

    def infer(self):
        pass

    @classmethod
    def parse(cls, stream):
        assignable = {'const' : False, 'var' : True}[stream.pop()]
        if stream.peek() not in ('const', 'var'):
            error.token(stream.pop(), "`const` / `var` not followed by `const` / `var`.")
        editable = {'const' : False, 'var' : True}[stream.pop()]

        name = stream.pop()

        lifetime = None
        lifetype = 'stmt'
        if stream.peekt().kind == 'lifeopen':
            stream.expect('<')

            sign = stream.peek() == '-'
            if sign: stream.expect('-')

            lifetime = int(stream.pop()) * (-1 if sign else 1)

            if stream.peek() == 's':
                stream.expect('s')
                lifetype = 'sec'

            stream.expect('>')

        if stream.peek() != '=':
            error.token(stream.pop(), "Expected `=`.")
        stream.pop()

        expr = AstExpr.parse(stream)
        return cls(editable, assignable, name, expr, lifetime, lifetype)

    def run(self, ctx):
        init = self.expr.run(ctx)

        init.editable = self.editable
        init.assignable = self.assignable

        ctx.scope[self.name] = init
        ctx.scope[self.name].parent = self

        #register local creation time
        ctx.scope[self.name].time_born = time.time()
        




@dc
class AstAssign:
    dst : typing.Any
    src : typing.Any

    def infer(self): pass

    @classmethod
    def parse(cls, stream):
        dst = AstScopeAccess.parse(stream)
        stream.expect('=')
        src = AstExpr.parse(stream)

        return cls(dst, src)

    @classmethod
    def parse_index_access(cls, stream):
        dst = AstIndexAccess.parse(stream)

        # for `array[index]?`
        if stream.peek() != '=':
            return dst

        stream.expect('=')
        src = AstExpr.parse(stream)

        return cls(dst, src)

    def run(self, ctx):
        dst = self.dst.run(ctx, lvalue=True)
        src = self.src.run(ctx)

        dst.content = src.content
        dst.kind    = src.kind

        dst._assign(ctx)

@dc
class AstFuncDef:
    name : str
    params : list[str]
    body : AstBlock | AstExpr

    @classmethod
    def parse(cls, stream):
        stream.pop()
        name = stream.pop()

        params = []
        while stream.peek() != '=>':
            params.append(stream.pop())
            if stream.peek() == ',':
                stream.expect(',')
        stream.expect('=>')

        if stream.peek() == '{': #}
            body = AstBlock.parse(stream)
        else:
            body = AstExpr.parse(stream)

        return cls(name, params, body)


    def run(self, ctx):
        ctx.scope[self.name] = obj.Value(self, kind='func')

    def call(self, ctx, params):
        ctx.push_scope()

        for k,v in zip(self.params, params):
            ctx.scope[k] = v

        res = self.body.run(ctx)

        ctx.pop_scope()
        return res






@dc
class AstStmt:
    sub : typing.Any
    eos : str

    def _is_func_keyword(word):
        i = 0
        for char in 'function':
            if word[i] == char:
                i += 1

            if len(word) == i:
                return True

        return False
            

    def infer(self):
        self.sub.infer()

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
            case 'when', _:
                sub = AstWhen.parse(stream)
                need_eos = type(sub) is AstExpr

            case _, '[': #]
                sub = AstAssign.parse_index_access(stream)

            case _, '=':
                sub = AstAssign.parse(stream)

            case x, name if cls._is_func_keyword(x) and name.isalpha():
                sub = AstFuncDef.parse(stream)
                need_eos = False

            case x, y if all(i in ('const', 'var') for i in (x, y)):
                sub = AstDecl.parse(stream)

            case x: 
                sub = AstExpr.parse(stream)


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

        return res

@dc
class AstProg:
    content : AstBlock

    
    @classmethod
    def parse(cls, stream):
        return cls(AstBlock.parse(stream, prog=True))

    def run(self, ctx):
        builtin.inject(ctx)

        self.content.run(ctx)

    def infer(self):
        self.content.infer()
            



