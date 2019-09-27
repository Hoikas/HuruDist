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

from _constants import *
import functools
import io
import logging
import multiprocessing, multiprocessing.pool
import pathlib
from PyHSPlasma import *
import subprocess
import _utils
import _workers

from yaml import load, dump
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

def find_python_dependencies(py_exe, module_name, scripts_path):
    assert py_exe is not None

    plasma_python_path = scripts_path.joinpath("plasma")
    args = (str(py_exe), str(_utils.find_python2_tools()), "get_imports", str(module_name),
            str(scripts_path), str(plasma_python_path))
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
    if result.returncode == PyToolsResultCodes.success:
        with io.StringIO(result.stdout) as strio:
            for py_abs_path in strio:
                module_path = pathlib.Path(py_abs_path.rstrip())

                # Don't include any of the builtin engine-level code in python/plasma
                try:
                    module_path.relative_to(plasma_python_path)
                except ValueError:
                    pass
                else:
                    continue
                try:
                    module_path = module_path.relative_to(scripts_path)
                except ValueError:
                    continue
                else:
                    yield str(module_path)
    else:
        if result.returncode == PyToolsResultCodes.traceback:
            logging.error(f"Python module {module_name} failed to import\n{result.stdout}.")
        elif result.returncode == PyToolsResultCodes.file_not_found:
            logging.warning(f"Python module {module_name} could not be found.")
        else:
            logging.warning(f"Unhandled error {result.returncode} when importing Python module {module_name}.\n{result.stdout}")

def log_exception(ex):
    logging.exception(ex)

def make_asset_path(args, asset_category, asset_filename):
    subdir = client_subdirectories[asset_category]
    asset_source_path = args.source.joinpath(subdir, asset_filename)

    # If this is a Python or SDL file, we will allow falling back to a specified moul-scripts repo...
    # We avoid doing this for .age, .fni, and .csv due to the un-WDYS'd nature of those files.
    if asset_category in {"python", "sdl"} and args.moul_scripts and not asset_source_path.exists():
        asset_source_path = args.moul_scripts.joinpath(subdir, asset_filename)
    return asset_source_path

def main(args):
    client_path = args.source
    dat_path = args.source.joinpath("dat")
    age_path = dat_path.joinpath(f"{args.age_name}.age")
    if not age_path.exists():
        logging.critical(f"Age file '{age_path}' does not exist.")
        return False

    if args.moul_scripts and not args.moul_scripts.exists():
        logging.error(f"Script path '{args.moul_scripts}' does not exist.")

    age_info = plAgeInfo()
    try:
        age_info.readFromFile(str(age_path))
    except IOError as ex:
        logging.exception(ex)
        return False

    # Collect a list of all age pages to be abused for the purpose of finding its resources
    # Would be nice if this were a common function of libHSPlasma...
    room_pages = [dat_path / age_info.getPageFilename(i, pvMoul) for i in range(age_info.getNumPages())]
    common_pages = [dat_path / age_info.getCommonPageFilename(i, pvMoul) for i in range(age_info.getNumCommonPages(pvMoul))]
    all_pages = set(room_pages + common_pages)
    missing_pages = set()
    logging.info(f"Found {len(all_pages)} Plasma pages.")

    # Before we begin, check against the file system to see what files are available.
    for page in all_pages:
        if not page.exists():
            logging.warning(f"Age Page '{page.name}' is missing from the client...")
            missing_pages.add(page)
    all_pages -= missing_pages

    # We want to get the age dependency data. Presently, those are the python and ogg files.
    # Unfortunately, libHSPlasma insists on reading in the entire page before allowing us to
    # do any of that. So, we will execute this part in a process pool.
    dlevel = plDebug.kDLWarning if args.verbose else plDebug.kDLNone
    iterable = [(i, dlevel) for i in all_pages]
    pool = multiprocessing.pool.Pool()
    results = pool.starmap(_workers.find_page_externals, iterable)

    # What we have now is a list of dicts, each nearly obeying the output format spec.
    # Now, we have to merge them... ugh.
    logging.info(f"Merging results from {len(results)} dependency lists...")
    output = _utils.coerce_asset_dicts(results)

    # Now we have all of this age's PythonFileMod scripts. However, those scripts in turn may
    # depend on other python modules, so we need to look for them.
    py_exe = args.python if args.python else _utils.find_python_exe()
    if py_exe:
        python_path = (args.moul_scripts if args.moul_scripts else args.source).joinpath("Python")
        known_python_files = tuple(output.get("python", {}).keys())
        for py_file_name in known_python_files:
            for i in find_python_dependencies(py_exe, pathlib.Path(py_file_name).stem, python_path):
                output["python"].setdefault(i, {})
    else:
        logging.warning("Age Python may not be completely bundled!")

    # Add in the .age, .fni, and .prp files. Note that the .csv is detected as a dependency.
    data = output.setdefault("data", {})
    for i in all_pages:
        data[str(i.relative_to(dat_path))] = {}
    data[f"{args.age_name}.age"] = {}
    if age_info.seqPrefix > 0:
        data[f"{args.age_name}.fni"] = {}

    # OK, now everything is (mostly) sane. Only exception is that find_page_external gives us a ton
    # of "suggestions" for which SDL files we may want. These files may or may not exist. Further,
    # we might be in some weird ass-environment where the other dependencies (py, ogg) don't exist.
    # So, let's handle that now.
    missing_assets = []
    logging.info("Beginning final pass over assets...")
    for asset_category, assets in output.items():
        for asset_filename, asset_dict in assets.items():
            asset_source_path = make_asset_path(args, asset_category, asset_filename)
            if not asset_source_path.exists():
                missing_assets.append((asset_category, asset_filename))
                if asset_dict.get("optional", False):
                    logging.debug(f"Unable to locate optional asset '{asset_source_path.name}'.")
                else:
                    logging.warning(f"Asset '{asset_source_path.name}' is missing from the client.")
                continue

            # Fill in some information from the filesystem.
            stat = asset_source_path.stat()
            asset_dict["modify_time"] = int(stat.st_mtime)
            asset_dict["size"] = stat.st_size

            # Command line specs
            asset_dict["dataset"] = args.dataset.name
            if args.distribute is not None:
                asset_dict["distribute"] = args.distribute.name

            # Now we submit slow operations to the process pool.
            def pool_cb(asset_dict, key, value):
                asset_dict[key] = value
            md5_complete = functools.partial(pool_cb, asset_dict, "hash_md5")
            sha2_complete = functools.partial(pool_cb, asset_dict, "hash_sha2")

            pool.apply_async(_workers.hash_md5, (asset_source_path,),
                             callback=md5_complete, error_callback=log_exception)
            pool.apply_async(_workers.hash_sha2, (asset_source_path,),
                             callback=sha2_complete, error_callback=log_exception)

    # Discard any missing thingos from our asset map and it will be very nearly final.
    for asset_category, asset_filename in missing_assets:
        output[asset_category].pop(asset_filename)
    for asset_category in tuple(output.keys()):
        if not output[asset_category]:
            output.pop(asset_category)

    # Wait for the pool to finish
    pool.close()
    pool.join()

    # Time to produce the bundle
    logging.info("Producing final asset bundle...")
    with _utils.OutputManager(args.destination) as outfile:
        for asset_category, assets in output.items():
            src_subdir = client_subdirectories[asset_category]
            dest_subdir = asset_subdirectories[asset_category]
            for asset_filename, asset_dict in assets.items():
                asset_dict["source"] = str(pathlib.PureWindowsPath(dest_subdir, asset_filename))
                asset_source_path = make_asset_path(args, asset_category, asset_filename)
                asset_dest_path = pathlib.Path(dest_subdir, asset_filename)
                outfile.copy_file(asset_source_path, asset_dest_path)

        logging.info("Writing bundle YAML...")
        outfile.write_file("Contents.yml", dump(output, indent=4, Dumper=Dumper))

    return True
