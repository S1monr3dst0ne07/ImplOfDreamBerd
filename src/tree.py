
import typing
import time
import regex
from dataclasses import dataclass as dc

import lex
import error
import sym
import obj
import builtin
import conf
import dbx



deleted_features = set()
deleted_values   = list()

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

    def order(self):
        for i, param in enumerate(self.params):
            self.params[i] = param.order()


    def _can_param_token(stream):
        match stream.peekt().kind:
            case 'numb' | 'iden' | 'quote':
                return True

            case _:
                return False

    @classmethod
    def parse(cls, stream):
        iden = stream.pop()
        params = []

        # syntax sugar for `subj.verb(obj...)` => `verb(subj, obj...)`
        subj = None
        if stream.peek() == '.':
            stream.expect('.')
            subj, iden = iden, stream.pop()

        #if stream.peek().isdigit() or stream.peekt().content not in (sym.op + sym.un_op + sym.block):
        if cls._can_param_token(stream):
            # this check is needed to prevent `x + 5` from
            # being parsed as `x(+) 5`

            while stream.peekt().kind not in ('eos', 'debug'):
                params.append(AstExpr.parse(stream))
                if stream.peek() != ',': break
                stream.expect(',')

        return cls(iden, subj, params)

    def _var_lookup(self, ctx, iden):
        if iden in ctx.eternal: return ctx.eternal[iden]

        if iden not in ctx.scope:
            error.error(f"Identifier `{iden}` does not exist in scope.")
    
        var = ctx.scope[iden]
        if not var.alive():
            error.error(f"Trying to access variable `{iden}` but it's dead :(")
    
        return ctx.scope[iden]

    def _check_string_without_quote(self, ctx):
        return (self.iden not in ctx.eternal and self.iden not in ctx.scope)

    def _process_string_without_quote(self, ctx):
        segments = [self.iden] + [x.run(ctx).render() for x in self.params]
        return obj.Value(content=[
            obj.Value(content=char, kind='char')
            for char in " ".join(segments) 
                #space information is lost during parsing.
                #retaining it would require so, so, so much work.
                #plus the example don't show multi-space quoteless strings,
                # so what do i care.
        ], kind='string')


    def run(self, ctx, lvalue=False):
        if self._check_string_without_quote(ctx) and not lvalue: 
            return self._process_string_without_quote(ctx)

        params = (
            ([self._var_lookup(ctx, self.subj)] if self.subj is not None else []) + 
             [x.run(ctx) for x in self.params]
        )
        value = self._var_lookup(ctx, self.iden)

        if value.kind == 'metafunc':
            # calls as function if type if iden in scope is metafunc
            return value.content(*params)

        if value.kind == 'signal':
            if len(params) > 0:
                value.content = params[0]

            return value.content

        #if the parameter counts don't match, it's a function literal
        func_run_continue = lambda: value.content.call(ctx, params)
        if value.kind == 'func' and len(params) == len(value.content.params):
            if value.content._async:
                ctx.running_async = True
                ctx.running_async_continue = func_run_continue
            else:
                return func_run_continue()

        #otherwise it has to have been a variable access
        return value

    def vars(self):
        return [self.iden] + [x.vars() for x in self.params]



@dc
class AstLitArray:
    elems : list["AstExpr"]

    def order(self):
        for i, elem in enumerate(self.elems):
            self.elems[i] = elem.order()

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
class AstLitDict:
    def order(self): pass

    @classmethod
    def parse(cls, stream):
        stream.expect("{")
        stream.expect("}")

        return cls()

    def run(self, ctx):
        return obj.Value(content={}, kind='dict')

@dc
class AstIndexAccess:
    name : str
    index : "AstExpr"

    def order(self):
        self.index = self.index.order()

    @classmethod
    def parse(cls, stream):
        name = stream.pop()
        stream.expect('[') #]
        index = AstExpr.parse(stream)
        stream.expect(']')

        return cls(name, index)

    def run(self, ctx, lvalue=False):
        value = ctx.scope[self.name]
        index = self.index.run(ctx)

        match value.kind:
            case 'array':
                if index.kind not in ('int', 'float'):
                    error.error(f"Array access with non-numeric index: `{index.content}`")

                index = index.content + 1
                if lvalue and index not in value.content:
                    value.content[index] = obj.Value(None, 'null')
                return value.content[index]

            case 'dict':
                if index not in value.content:
                    value.content[index] = obj.Value(None, 'undefined')
                return value.content[index]
        



@dc
class AstLeaf:
    META_VALUES = (AstScopeAccess, AstLitArray, AstLitDict, AstIndexAccess, dbx.AstHtml)
    value : typing.Any

    def infer(self): pass
    def order(self):
        if type(self.value) in self.META_VALUES:
            self.value.order()

        return self

    @staticmethod
    def _compute_quote_size(token):
        size = 0
        for char in token.content:
            if char == "'": size += 1
            if char == '"': size += 2

        return size

    def _format_string(self, ctx):
        currency = conf.locale_currency_mapper[conf.Config.locale]
        string = self.value.render()
        if currency.symbol not in string: return self.value

        out = []
        symbol_state = False
        reading_name = False
        name = ""

        match currency.kind:
            case 'prefix':
                for char in string:
                    if char == '{' and symbol_state: #}
                        reading_name = True
                        continue
                    if char == '}' and reading_name:
                        reading_name = False
                        if name in ctx.scope:
                            out.pop(-1) #remove prefix
                            out.append(ctx.scope[name].render())
                        else:
                            out.append("{")
                            out.append(name)
                            out.append("}")

                        continue
                        
                    if reading_name: name += char
                    else: out.append(char)
                    symbol_state = char == currency.symbol
            case 'suffix':
                for char in string:
                    if char == '{': #}
                        reading_name = True
                        continue
                    if char == '}' and reading_name:
                        reading_name = False
                        symbol_state = True
                        continue

                    if symbol_state:
                        symbol_state = False
                        if char == currency.symbol:
                            if name in ctx.scope:
                                out.append(ctx.scope[name].render())
                                continue
                            else:
                                out.append("{")
                                out.append(name)
                                out.append("}")
                        
                    if reading_name: name += char
                    else: out.append(char)
            case 'infix':
                for char in string:
                    if reading_name and char == currency.symbol:
                        symbol_state = True
                    if char == '{': #}
                        reading_name = True
                        continue
                    if char == '}' and reading_name:
                        reading_name = False

                        iden, field = name.split(currency.symbol) 
                        def _extract():
                            if not symbol_state: return False
                            if iden not in ctx.scope: return False
                            value = ctx.scope[iden]
                            if value.kind != 'dict': return False
                            decoded = {k.render() : v for k,v in value.content.items()}
                            if field not in decoded: return False

                            out.append(decoded[field].render())
                            return True
                        
                        if _extract():
                            continue
                        else:
                            out.append('{')
                            out.append(name)

                    if reading_name: name += char
                    else: out.append(char)

            case x:
                error.internal(f"undefined currency kind: `{x}`")


        return obj.Value(
            content=[
                obj.Value(content = x, kind = 'char')
                for x in "".join(out)],
            kind = 'string'
        )

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
        match stream.peekt().kind:
            case 'numb':
                leaf = int(stream.pop())
                kind = 'int'
                if stream.peekt().kind == 'dot':
                    stream.pop()
                    leaf += float(f"0.{stream.pop()}")
                    kind = 'float'
                
                value = obj.Value(leaf, kind)

            case 'quote': 
                value = obj.Value(
                    content = [
                        obj.Value(content = x, kind = 'char') 
                        for x in cls._parse_string(stream)
                    ],
                    kind = 'string'
                )
                
            case 'arrayopen':
                value = AstLitArray.parse(stream)
            case 'blockopen':
                value = AstLitDict.parse(stream)

            case 'iden' | 'sym': 
                if stream.lookhead(2)[1].kind == 'arrayopen':
                    value = AstIndexAccess.parse(stream)
                else:
                    value = AstScopeAccess.parse(stream)

            case 'lifeopen':
                value = dbx.AstHtml.parse(stream)

            case x: error.error(f"Unknown leaf kind: {stream.popt()}")

        return cls(value)

    def run(self, ctx):
        if type(self.value) in self.META_VALUES:
            return self.value.run(ctx)

        #renamed literal number
        numb_name = str(self.value.content)
        if self.value.kind == 'int' and numb_name in ctx.scope:
            return ctx.scope[numb_name]

        #format string
        if self.value.kind == 'string':
            return self._format_string(ctx)

        return self.value

    def vars(self):
        if type(self.value) is obj.Value:
            return []

        return self.value.vars()


@dc
class AstUn:
    op : str
    sub : AstLeaf

    def order(self): 
        return self

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

    def extract(self, parent):
        if type(self.right) is not AstExpr: return (self, parent)

        other = self.right.extract(self)
        return other if other[0].space > self.space else (self, parent)


    def infer(self): pass
    def order(self):
        # after parsing, the expression tree is maximally unballanced,
        # meaning it looks like this:
        #   ()
        #  / ()
        #   / \...
        # we extract the node with least precedence,
        #  then pivot it and make it the new root node.
        #  this process is repeated recursively until 
        #  the tree is balanced based on the precedence.

        new, parent = self.extract(None)
        old = self

        if new != old:
            # you can work these operations out on paper if you think about it really really hard.
            # i'm not even gonna try and explain them.
            # rest assured, they balance the tree.
            orphan = new.left
            new.left = old
            parent.right = orphan

        #now recurse
        new.left.order()
        new.right.order()

        return new

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


        l = left.content
        r = right.content
        kind = None

        def string_to_number_cast():
            nonlocal l, r
            _convert = lambda x: float(x) if '.' in x else int(x)
            if left.kind  == 'string': l = _convert(left.render())
            if right.kind == 'string': r = _convert(right.render())

        match self.op:
            # accursed by ye, brendan eich, for making javascript.
            # and also for being a homophobic (and prolly transphobic, let's be real) bastard.
            case '+': 
                if 'string' in (left.kind, right.kind):
                    kind = 'string'
                    res = [
                        obj.Value(content=char, kind='char') 
                        for char in left.render() + right.render()
                    ]
                elif all(x in ('float', 'int') for x in (left.kind, right.kind)):
                    kind = 'float' if 'float' in (left.kind, right.kind) else 'int'
                    res = l + r
                elif left.kind == right.kind == 'array':
                    kind = left.kind
                    offset = max(l.keys()) - min(r.keys()) + 1
                    res = l | { k + offset : v for k,v in r.items() }
                elif left.kind == right.kind == 'dict':
                    kind = left.kind
                    res = l | r
                else:
                    error.error(f"Cannot add `{left.render()}` and `{right.render()}` because they are containers and types do not match.")

            case x if x in ('-', '*', '/', '^'):
                string_to_number_cast()
                if any(x.kind in ('dict', 'array') for x in (left, right)):
                    _error(x)

                match x:
                    case '-': res = l - r
                    case '*': res = l * r
                    case '/': res = (l / r) if r != 0 else None
                    case '^': res = l ** r

                match res:
                    case float(): kind = 'float'
                    case int():   kind = 'int'
                    case None:    kind = 'undefined' # aka NaN
                    case x: error.internal("binary expression on numeric values yielded non-numeric type.")

                if 'magictime' in (left.kind, right.kind):
                    kind = 'magictime'

            case '====':
                #cursed ast comparison
                kind = 'bool'
                res = self.left == self.right

            case '===': # tight equality
                kind = 'bool'
                res = l == r

            case '==': # loose equality
                kind = 'bool'
                string_to_number_cast()
                res = l == r

            case '=': # even looser equality
                kind = 'bool'
                string_to_number_cast()
                if type(l) is float: l = round(l)
                if type(r) is float: r = round(r)
                res = l == r

            case ';=': res = l != r
            case '<': res = l < r
            case '>': res = l > r

            case x: _error(x)

        def _error(x):
            error.error(f"Operation `{x}` is not defined for `{left.render()}` and `{right.render()}`.")

        return obj.Value(content=res, kind=kind)

    def vars(self):
        return self.left.vars() + self.right.vars()





@dc
class AstIf:
    cond : AstExpr
    body : "AstStmt"

    def order(self): 
        self.cond = self.cond.order()
        self.body.order()
    def infer(self):
        self.body.infer()

    @classmethod
    def parse(cls, stream):
        if 'if' in deleted_features:
            error.error("Feature `if` has been deleted.")

        stream.expect('if')
        cond = AstExpr.parse(stream)
        body = AstStmt.parse(stream)
        return cls(cond, body)

    def run(self, ctx):
        cond = self.cond.run(ctx).content
        if cond not in (True, False):
            error.error(f"Indecisive condition: `{cond.render()}`")

        if cond:
            self.body.run(ctx)

@dc
class AstWhen:
    cond : AstExpr
    body : "AstStmt"

    def order(self): 
        self.cond = self.cond.order()
        self.body.order()
    def infer(self):
        self.body.infer()

    @classmethod
    def parse(cls, stream):
        if 'when' in deleted_features:
            error.error("Feature `when` has been deleted.")

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

    def order(self):
        for stmt in self.stmts:
            stmt.order()

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
            offset_offset = (-1 if timetravel else 1)
            offset = offset_offset
            for _ in range(abs(decl.lifetime)):
                self.stmt_alive[index + offset].add(decl.name)
                offset += offset_offset

        #compute compliment (insert deep quote about yin and yang or smth)
        for index, stmt in enumerate(self.stmts):
            self.stmt_dead.append(set(
                varname for varname in [x.sub.name for x in relevent_stmts]
                if varname not in self.stmt_alive[index]
            ))

        #recursive infer
        for stmt in self.stmts:
            stmt.infer()


    def run(self, ctx, index=0):
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
        step = index + ctx.offset

        #scheduler base case
        if len(self.stmts) == step or step < 0:
            return ctx.scheduler(lambda: res)

        #pass continuation into context scheduler.
        # this is some fucking haskell level programming right here.
        return ctx.scheduler(lambda: self.run(ctx, step))


@dc
class AstClass:
    name : str
    body : "AstBlock"

    def order(self): self.body.order()
    def infer(self): self.body.infer()

    @classmethod
    def parse(cls, stream):
        if 'class' in deleted_features:
            error.error("Feature `class` has been deleted.")

        stream.pop() # `class` or `className`

        name = stream.pop()
        body = AstBlock.parse(stream)
        return cls(name, body)

    def run(self, ctx):
        ctx.scope[self.name] = obj.Value(
            content = { 
                'ast': self, 
                'used': False  #has class object been instantiated?
            },
            kind = 'metaclass',
        )







@dc
class AstDecl:
    editable   : bool
    assignable : bool
    names : set[str]
    name : str # "proper name"
    expr : AstExpr

    lifetime : int | None
    lifetype : typing.Literal['default', 'stmt', 'sec', 'infty'] 

    # "immutable data"
    eternal : bool

    # how many exclaimation mark
    priority : int = 0


    def order(self): self.expr = self.expr.order()
    def infer(self): pass

    @staticmethod
    def _extract_names(stream):
        if stream.peek() == '[': #]
            stream.expect('[')
            first = AstDecl._extract_names(stream)
            stream.expect(',')
            second = AstDecl._extract_names(stream)
            stream.expect(']')
            return first | second

        else:
            return { stream.pop() }


    @classmethod
    def parse(cls, stream):
        first_storage_type = stream.pop()
        if stream.peek() not in ('const', 'var'):
            error.token(stream.pop(), "`const` / `var` not followed by `const` / `var`.")
        second_storage_type = stream.pop()

        if 'const' in deleted_features and 'const' in (first_storage_type, second_storage_type):
            error.error("Feature `const` has been deleted.")
        if 'var' in deleted_features and 'var' in (first_storage_type, second_storage_type):
            error.error("Feature `var` has been deleted.")

        assignable = {'const' : False, 'var' : True}[first_storage_type]
        editable   = {'const' : False, 'var' : True}[second_storage_type]

        # new for 2023!
        eternal = False
        if not assignable and not editable and stream.peek() == 'const':
            stream.expect('const')
            eternal = True
            
        names = cls._extract_names(stream)

        lifetime = None
        lifetype = 'default'

        if stream.peekt().kind == 'lifeopen':
            lifetype = 'stmt'
            stream.expect('<')

            if stream.peek() == 'Infinity':
                stream.pop()
                lifetype = 'infty'

            sign = stream.peek() == '-'
            if sign: stream.expect('-')

            if stream.peek().isdigit():
                lifetime = int(stream.pop()) * (-1 if sign else 1)

            if stream.peek() == 's':
                stream.expect('s')
                lifetype = 'sec'

            stream.expect('>')

        #type annotation
        if stream.peek() == ':':
            stream.expect(':')
            word = stream.pop()

            reregegexx = regex.compile("Reg(ular)?[eE]x(p(ression)?)?")
            if not reregegexx.match(word):
                while stream.peek() != '=': stream.pop()
            else:
                stream.expect("<")
                while stream.pop() != '>': pass

        stream.expect('=')

        expr = AstExpr.parse(stream)
        return cls(
            editable=editable, 
            assignable=assignable, 
            names=names, 
            name = list(names)[0],
            expr=expr, 
            lifetime=lifetime, 
            lifetype=lifetype, 
            eternal=eternal
        )



    def run(self, ctx):
        init = self.expr.run(ctx)

        init.editable = self.editable
        init.assignable = self.assignable

        for name in self.names:
            # make priority is followed
            if name in ctx.scope:
                if ctx.scope[name].priority > self.priority:
                    return

            ctx.scope[name] = init
            ctx.scope[name].lifetime = self.lifetime
            ctx.scope[name].lifetype = self.lifetype
            ctx.scope[name].priority = self.priority

            # register local creation time
            ctx.scope[name].time_born = time.time()

            # upload variable to database if eternal
            if self.eternal: ctx.eternal_upload(name)
            




@dc
class AstAssign:
    dst : "AstScopeAccess | AstIndexAccess"
    src : "AstExpr"

    def order(self): 
        self.dst.order()
        self.src = self.src.order()

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

        dst._pre_mut()

        dst.content = src.content
        dst.kind    = src.kind

        dst._assign(ctx)

@dc
class AstFuncDef:
    name : str
    params : list[str]
    body : AstBlock | AstExpr

    _async : bool

    def order(self): 
        new = self.body.order()
        if type(self.body) is AstExpr:
            self.body = new

    def infer(self):
        self.body.infer()

    @classmethod
    def parse(cls, stream, _async=False):
        if 'function' in deleted_features:
            error.error("Functions have been deleted.")

        stream.pop()
        name = stream.pop()

        params = []
        while stream.peek() != '=':
            params.append(stream.pop())
            if stream.peek() == ',':
                stream.expect(',')
        stream.expect('=')
        stream.expect('>')

        if stream.peek() == '{': #}
            body = AstBlock.parse(stream)
        else:
            body = AstExpr.parse(stream)

        return cls(name, params, body, _async)

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
class AstDelete:
    target : "AstExpr | None"

    @classmethod
    def parse(cls, stream):
        if 'delete' in deleted_features:
            error.error("Deletions have themselves been deleted.")

        stream.expect('delete')

        target = None
        match stream.peek():
            case x if x in ('if', 'when', 'class', 'const', 'var', 'delete'):
                deleted_features.add(x)
                stream.pop()

            case x if AstStmt._is_func_keyword(x): 
                deleted_features.add('function')
                stream.pop()

            case x:
                target = AstExpr.parse(stream)

        return cls(target)

    def order(self): 
        if self.target is not None:
            self.target.order()
    def infer(self): pass

    def run(self, ctx):
        if self.target is not None:
            deleted_values.append(self.target.run(ctx))


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
            

    def infer(self): self.sub.infer()
    def order(self): self.sub.order()

    @classmethod
    def parse(cls, stream):
        indent = stream.space()
        if indent % 3 != 0:
            error.token(stream.peekt(), "Invalid indentation. All indents must be 3 spaces long.")

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

            case ('class', _) | ('className', _):
                sub = AstClass.parse(stream)
                need_eos = False

            case 'delete', _:
                sub = AstDelete.parse(stream)

            case _, '[': #]
                sub = AstAssign.parse_index_access(stream)

            case _, '=':
                sub = AstAssign.parse(stream)

            case x, name if cls._is_func_keyword(x) and name.isalpha():
                sub = AstFuncDef.parse(stream)
                need_eos = type(sub.body) is AstExpr

            case 'async', _: #OMG LIKE DA BACKROOMS (sorry)
                stream.expect('async')
                sub = AstFuncDef.parse(stream, _async=True)
                need_eos = type(sub.body) is AstExpr

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

        if type(sub) is AstDecl:
            sub.priority = eos.count('!') - eos.count('¡')

        stream.space()
        return cls(sub, eos)

    def run(self, ctx):
        res = self.sub.run(ctx)
        
        match self.eos:
            case "?": print(f"[DEBUG] {res.render()}")

        return res

    


@dc
class AstProg:
    @dc
    class File:
        prog : AstBlock
        ctx  : obj.Ctx
        exports: list[tuple[
            str, # function name
            str, # target file
        ]]

    files : dict[str, AstBlock]

    @staticmethod
    def _anon_file_name_gen():
        i = 0
        while True:
            yield f"anon_func_{i}"
            i += 1

    @classmethod
    def load(cls, src):
        name = "main"
        name_gen = AstProg._anon_file_name_gen()

        files = {}
        buffer = []
        exports = []

        # parse files separately
        def emit(line):
            nonlocal buffer, name, files, exports
            if name == "": name = next(name_gen)
            if buffer != []:
                stream = lex.tokenize("\n".join(buffer))
                files[name] = AstProg.File(
                    prog=AstBlock.parse(stream, prog=True), #program
                    ctx=obj.Ctx(), #program execution context
                    exports=exports, #exports of the program
                )
            buffer = []
            exports = []
            name = line.strip("= ")

        for line in src.split('\n'):
            if line.startswith('=' * 5): emit(line)
                # technical info: the import statement doesn't do anything.
            elif line.startswith('import'): pass
            elif line.startswith('export'):
                _, func_name, _, target = line.strip('!').split(' ')
                target = target.strip('"')
                exports.append((func_name, target))
            else: buffer.append(line)
        emit("")
    
        return cls(files)


    def run(self):
        for name, file in self.files.items():
            self.run_file(file)

        return self.files

    def run_file(self, file : "AstProg.File"):
        self.run_prog(file.prog, file.ctx)

        #execute exports
        for func, target in file.exports:
            value = file.ctx.scope[func]
            self.files[target].ctx.scope[func] = value

    def run_prog(self, prog, ctx):
        prog.order() #whitespace based binary expression reordering
        prog.infer() #lifetime inferrence pass 

        builtin.inject(ctx)

        ctx.load() #load persistent variables from database
        prog.run(ctx)
        ctx.save() #save persistent variables back to database

            



