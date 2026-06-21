import sys

import lex
import tree
import obj


def main():
    path = sys.argv[1]

    stream = lex.tokenize(path)
    root = tree.AstProg.parse(stream)
    ctx = obj.Ctx()
    root.run(ctx)



if __name__ == "__main__":
    main()

