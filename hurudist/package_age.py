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

import functools
import logging
import multiprocessing, multiprocessing.pool
import pathlib
from PyHSPlasma import *
import _utils
import _workers

from yaml import load, dump
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

def log_exception(ex):
    logging.exception(ex)

def main(args):
    client_path = pathlib.Path(args.source)
    dat_path = client_path / "dat"
    age_path = dat_path / f"{args.age_name}.age"
    if not age_path.exists():
        logging.critical(f"Age file '{age_path}' does not exist.")
        return False

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
    logging.debug(f"Found {len(all_pages)} pages.")

    # Before we begin, check against the file system to see what files are available.
    for page in all_pages:
        if not page.exists():
            logging.warning(f"Age Page '{page.name}' is missing from the client...")
            missing_pages.add(page)
    all_pages -= missing_pages

    # We want to get the age dependency data. Presently, those are the python and ogg files.
    # Unfortunately, libHSPlasma insists on reading in the entire page before allowing us to
    # do any of that. So, we will execute this part in a process pool.
    pool = multiprocessing.pool.Pool()
    results = pool.map(_workers.find_page_externals, all_pages)

    # What we have now is a list of dicts, each nearly obeying the output format spec.
    # Now, we have to merge them... ugh.
    output = {}
    logging.debug(f"Merging results from {len(results)} dependency lists...")
    for result in results:
        for dependency_category, dependencies in result.items():
            if not dependency_category in output:
                output[dependency_category] = dependencies
            else:
                output_category = output[dependency_category]
                for dependency_name, dependency_dict in dependencies.items():
                    output_dict = output_category.setdefault(dependency_name, dependency_dict)
                    if "options" in output_dict:
                        output_dict["options"].update(dependency_dict.get("options", set()))

    # Add in the .age, .fni, and .prp files. Note that the .csv is detected as a dependency.
    data = output.setdefault("data", {})
    for i in all_pages:
        data[str(i.relative_to(dat_path))] = {}
    data[f"{args.age_name}.age"] = {}
    data[f"{args.age_name}.fni"] = {}

    # OK, now everything is (mostly) sane. Only exception is that find_page_external gives us a ton
    # of "suggestions" for which SDL files we may want. These files may or may not exist. Further,
    # we might be in some weird ass-environment where the other dependencies (py, ogg) don't exist.
    # So, let's handle that now.
    missing_assets = []
    logging.debug("Beginning final pass over assets...")
    for asset_category, assets in output.items():
        subdir = _utils.client_subdirectories[asset_category]
        for asset_filename, asset_dict in assets.items():
            asset_source_path = client_path / subdir / asset_filename
            if not asset_source_path.exists():
                missing_assets.append((asset_category, asset_filename))
                if asset_dict.get("optional", False):
                    logging.debug(f"Unable to locate optional asset '{asset_source_path.name}'.")
                else:
                    logging.warning(f"Asset '{asset_source_path.name}' is missing from the client.")
                continue

            # Ensure the options element is not a set (looks nasty in YAML)
            asset_dict["options"] = list(asset_dict.get("options", []))

            # Fill in some information from the filesystem.
            stat = asset_source_path.stat()
            asset_dict["modify_time"] = int(stat.st_mtime)
            asset_dict["size"] = stat.st_size

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
    logging.debug("Producing final asset bundle...")
    with _utils.OutputManager(pathlib.Path(args.destination)) as outfile:
        for asset_category, assets in output.items():
            src_subdir = _utils.client_subdirectories[asset_category]
            dest_subdir = _utils.asset_subdirectories[asset_category]
            for asset_filename, asset_dict in assets.items():
                asset_dict["source"] = str(pathlib.PureWindowsPath(dest_subdir, asset_filename))
                asset_source_path = pathlib.Path(client_path, src_subdir, asset_filename)
                asset_dest_path = pathlib.Path(dest_subdir, asset_filename)
                outfile.copy_file(asset_source_path, asset_dest_path)

        logging.debug("Writing bundle YAML...")
        outfile.write_file("Contents.yml", dump(output, indent=4, Dumper=Dumper))

    return True
