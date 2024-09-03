#
# Copyright (c) Microsoft Corporation. All Rights Reserved.
#
from . import ivy
from . import ivy_interp as itp
from . import ivy_actions as act
from . import ivy_utils as utl
from . import ivy_logic_utils as lut
from . import tk_ui as ui
from . import ivy_logic as lg
from . import ivy_utils as iu
from . import ivy_module as im
from . import ivy_alpha
from . import ivy_art
from . import ivy_interp
from . import ivy_compiler
from . import ivy_isolate
from . import ivy_init

import sys

diagnose = iu.BooleanParameter("diagnose",False)

    
def usage():
    print("usage: \n  {} file.ivy".format(sys.argv[0]))
    sys.exit(1)

def check_module():
    # If user specifies an isolate, check it. Else, if any isolates
    # are specificied in the file, check all, else check globally.

    isolate = ivy_compiler.isolate.get()
    with im.module.copy():
        ivy_isolate.create_isolate(isolate) # ,ext='ext'


def main():
    ivy_init.read_params()
    iu.set_parameters({'show_compiled':'true'})
    if len(sys.argv) != 2 or not sys.argv[1].endswith('ivy'):
        usage()
    with im.Module():
        with utl.ErrorPrinter():
            ivy_init.source_file(sys.argv[1],ivy_init.open_read(sys.argv[1]),create_isolate=False)
            check_module()


if __name__ == "__main__":
    main()

