
from dataclasses import dataclass as dc
import subprocess

import tree
import obj
import error
import conf


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

        #check `class` and `className`
        for seg in segs:
            if type(seg) is not str: continue
            if "class" in seg:
                error.error("Identifier `class` in HTML tag.")
            if "className" in seg:
                error.error("Identifier `className` in HTML tag.")

        #rename `htmlClassName` to `class`
        for i, seg in enumerate(segs):
            if type(seg) is not str: continue
            segs[i] = seg.replace('htmlClassName', 'class')

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



def maybe_app(files):
    if 'main' not in files:
        return

    ctx = files['main'].ctx
    if 'App' not in ctx.scope:
        return

    app = ctx.scope['App']
    html = app.content.call(ctx, []).render()

    path = '.app'
    with open(path, 'w') as f:
        f.write(html)

    subprocess.run([conf.Config.webbrowser, path])



