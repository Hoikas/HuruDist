#    This file is part of HuruDist
#
#    HuruDist is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    HuruDist is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with HuruDist.  If not, see <http://www.gnu.org/licenses/>.

from _py2constants import *
import inspect
import os.path
import sys

def get_imports(py_module_name, *module_paths):
    """Gets a list of non-system imports"""

    # This could be done in an environment variable, but that seems kind of nasty.
    sys.path.extend(module_paths)

    if sys.version_info[0] == 2:
        import imp

        py_module_tup = imp.find_module(py_module_name)
        if not py_module_tup:
            sys.exit(TOOLS_FILE_NOT_FOUND)

        try:
            # This is nested because try... except... finally was not possible until Python 2.5
            try:
                the_py_module = imp.load_module(py_module_name, *py_module_tup)
            except:
                sys.excepthook(*sys.exc_info())
                sys.exit(TOOLS_MODULE_TRACEBACK)
        finally:
            py_module_tup[0].close()
    else:
        # This will work in Python 2.7 as well, but I want the above code to be well-tested in the
        # case of Python 2.3. The only reason I have this is because Python 3.x "helpfully" prints
        # a deprecation message.
        import importlib
        the_py_module = importlib.import_module(py_module_name)

    # Need to figure out now which modules are being imported from any of the paths...
    for module in sys.modules.values():
        try:
            this_module_path = inspect.getsourcefile(module)
        except:
            continue
        else:
            # This apparently happens for _hashlib.pyd wtf
            if not this_module_path:
                continue

            for module_search_path in module_paths:
                if os.path.commonprefix([module_search_path, this_module_path]):
                    sys.stdout.write(this_module_path)
                    sys.stdout.write("\n")
                    break

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("Not enough arguments.")
        sys.exit(TOOLS_INVALID_COMMAND)

    cmd = sys.argv[1]
    if not cmd in globals():
        sys.stderr.write("Invalid command '%s'" % cmd)
        sys.exit(TOOLS_INVALID_COMMAND)
    globals()[cmd](*sys.argv[2:])
    sys.exit(TOOLS_SUCCESS)
