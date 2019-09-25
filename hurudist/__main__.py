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

import _arguments
import importlib
import logging
import sys
import time

# Command to module name lookup table
commands = {
    "age": "package_age",
}

if __name__ == "__main__":
    start_time = time.perf_counter()
    args = _arguments.main_parser.parse_args()

    if args.quiet:
        level = logging.ERROR
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s", level=level)
    logging.debug("Starting H'uru Asset Distribution Manager __main__.")

    # Commands are just modules with a main() function
    module_name = commands[args.command]
    module = importlib.import_module(module_name)
    result = module.main(args)

    end_time = time.perf_counter()
    delta = end_time - start_time

    if not result:
        logging.error(f"H'uru Distribution Manager exiting with errors in {delta:.2f}s.")
    else:
        logging.info(f"H'uru Distribution Manager completed successfully {delta:.2f}s.")
