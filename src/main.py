import sys

import lex
import tree
import obj
import conf


def main():
    path = sys.argv[1]

    stream = lex.tokenize(path)
    root = tree.AstProg.parse(stream)

    root.infer() #lifetime inferrence pass 

    ctx = obj.Ctx()
    ctx.load() # load persistent variables from database

    root.run(ctx)

    ctx.save() #save them back again



if __name__ == "__main__":
    main()

