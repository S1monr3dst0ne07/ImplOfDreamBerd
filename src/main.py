import sys

import lex
import tree
import obj
import conf
import dbx


def main():
    path = sys.argv[1]


    try:
        root = tree.AstProg.load(path)
        files = root.run()

        # check and maybe open app
        dbx.maybe_app(files)
    except KeyboardInterrupt: 
        pass

    


if __name__ == "__main__":
    main()

