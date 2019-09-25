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

import argparse

program_description = "H'uru Asset Distribution Manager"
main_parser = argparse.ArgumentParser(description=program_description)

log_group = main_parser.add_mutually_exclusive_group()
log_group.add_argument("-q", "--quiet", action="store_true", help="Only print critical information")
log_group.add_argument("-v", "--verbose", action="store_true", help="Print verbose log output")

sub_parsers = main_parser.add_subparsers(title="Command", dest="command", required=True)

# Package age command argment parser
age_parser = sub_parsers.add_parser("age")
age_parser.add_argument("age_name", type=str)
age_parser.add_argument("source", type=str, help="Path to the root of the Plasma client")
age_parser.add_argument("destination", type=str, help="Path to store the resulting asset bundle")
