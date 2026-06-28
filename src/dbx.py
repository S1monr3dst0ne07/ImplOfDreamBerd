
from dataclasses import dataclass as dc

import tree
import obj


@dc
class AstHtml:
    segs : "list[AstExpr | str]"


    @classmethod
    def parse(cls, stream):
        segs = []

        buffer = ""

        # local streamer
        def peek():
            return stream.peekt(nocheck=True).content
        def pop():
            nonlocal buffer
            buffer += stream.peekt(nocheck=True).content
            return stream.popt(nocheck=True).content

        # not my proudest parser (scanner)
        tag_depth = 0
        def scan_tag():
            nonlocal tag_depth
            assert pop() == '<'
            if peek() == '/':
                pop()
                tag_depth -= 1
            else:
                tag_depth += 1

            #consume all parameters
            while True:
                match pop():
                    case '>': break
                    case '/': tag_depth -= 1

        def scan_embed_expr():
            nonlocal buffer
            segs.append(buffer)
            assert pop() == '{' #}
            segs.append(tree.AstExpr.parse(stream))
            assert pop() == '}'
            buffer = ""

        scan_tag()
        while tag_depth != 0:
            match peek():
                case '<': scan_tag()
                case '{': scan_embed_expr()
                #}
                case  _ : pop()

        segs.append(buffer)

        return cls(segs)
        

    def order(self):
        for i, seg in enumerate(self.segs):
            if type(seg) is not str:
                self.segs[i] = seg.order()

    def run(self, ctx):
        out = ""
        for seg in self.segs:
            if type(seg) is str:
                out += seg
            else:
                out += seg.run(ctx).render()

        return obj.Value(
            content = [
                obj.Value(
                    content = char,
                    kind = 'char'
                ) for char in out
            ],
            kind = 'string'
        )




