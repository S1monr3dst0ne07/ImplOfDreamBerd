import sys

import lex
import tree
import obj
import conf
import dbx
import rtf
import ai
import error

def main():
    path = sys.argv[1]

    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()

    # AI preprocessing
    if conf.Config.ai:
        error.Report.src = src
        src = ai.preprocess(src)

        if conf.Config.ai_writeback:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(src)

    # rich text preprocessing
    if path.endswith('.rtf'):
        src = rtf.preprocess(src)

    try:
        root = tree.AstProg.load(src)
        files = root.run()

        # check and maybe open app
        dbx.maybe_app(files)
    except KeyboardInterrupt: 
        pass

    


if __name__ == "__main__":
    main()

