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

from yaml import dump
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

def coerce_asset_dicts(all_outputs, all_pages, all_page_dicts):
    """Forcibly merges asset dicts, preserving only options keys"""
    for (age_name, page_path), age_page_dict in zip(all_pages, all_page_dicts):
        output = all_outputs[age_name]

        for asset_category, assets in age_page_dict.items():
            if not asset_category in output:
                output[asset_category] = assets
            else:
                output_category = output[asset_category]
                for asset_name, asset_dict in assets.items():
                    output_dict = output_category.setdefault(asset_name, asset_dict)
                    if "options" in output_dict:
                        new_options = set(output_dict["options"])
                        new_options.update(asset_dict.get("options", []))
                        output_dict["options"] = list(new_options)

def find_all_pages(all_outputs, data_path, *age_infos):
    # Collect a list of all age pages to be abused for the purpose of finding its resources
    # Would be nice if this were a common function of libHSPlasma...
    def _generate_page_paths(age_info):
        for i in range(age_info.getNumPages()):
            yield data_path.joinpath(age_info.getPageFilename(i, pvMoul))
        for i in range(age_info.getNumCommonPages(pvMoul)):
            yield data_path.joinpath(age_info.getCommonPageFilename(i, pvMoul))

    for age_info in age_infos:
        output = all_outputs.setdefault(age_info.name, {})
        data = output.setdefault("data", {})

        data[f"{age_info.name}.age"] = {}
        if age_info.seqPrefix > 0:
            data[f"{age_info.name}.fni"] = {}

        for page_path in _generate_page_paths(age_info):
            if page_path.exists():
                data[str(page_path.relative_to(data_path))] = {}
                yield (age_info.name, page_path)
            else:
                logging.warning(f"Age Page '{page_path.name}' is missing from the client...")

def find_page_externals(path, dlevel=plDebug.kDLNone):
    # Optimization: Textures.prp does not have any externals...
    if path.name.endswith("Textures.prp"):
        return {}

    plDebug.Init(dlevel)
    mgr = plResManager()
    page_info = mgr.ReadPage(path)
    location = page_info.location

    def sfx_flags_as_str(flags):
        if flags & plSoundBuffer.kStreamCompressed:
            yield "sound_stream"
        else:
            if flags & plSoundBuffer.kOnlyLeftChannel or flags & plSoundBuffer.kOnlyRightChannel:
                yield "sound_cache_split"
            else:
                yield "sound_cache_stereo"

    sfx_idx = plFactory.ClassIndex("plSoundBuffer")
    pfm_idx = plFactory.ClassIndex("plPythonFileMod")

    result = {
        "python": { f"{i.object.filename}.py": { "options": ["pfm"] }
                    for i in mgr.getKeys(location, pfm_idx) },

        "sfx": { i.object.fileName: { "options": list(sfx_flags_as_str(i.object.flags)) }
                 for i in mgr.getKeys(location, sfx_idx) },
    }

    # I know this isn't pretty, deal with it.
    if mgr.getKeys(location, plFactory.ClassIndex("plRelevanceRegion")):
        result["data"] = { f"{page_info.age}.csv": { } }

    return result

def find_pfm_externals(all_outputs, py_exe, py_path, sdl_path):
    def pool_cb(output, asset_category, source_path, asset_paths):
        for asset_path in asset_paths:
            asset_key = str(asset_path.relative_to(source_path))
            output.setdefault(asset_category, {}).setdefault(asset_key, {})

    with multiprocessing.pool.Pool() as pool:
        for output in all_outputs.values():
            pfm_names = [pathlib.Path(i).stem for i in output.get("python", {}).keys()]
            py_cb = functools.partial(pool_cb, output, "python", py_path)
            sdl_cb = functools.partial(pool_cb, output, "sdl", sdl_path)

            pool.apply_async(find_pfm_sdlmods, (sdl_path, pfm_names),
                             callback=sdl_cb, error_callback=log_exception)
            pool.apply_async(find_pfm_dependency_pymodules, (py_exe, py_path, pfm_names),
                             callback=py_cb, error_callback=log_exception)

        # Ensure all jobs finish
        pool.close()
        pool.join()

def find_pfm_sdlmods(source_path, pfm_names):
    sdl_mgrs = load_sdl_descriptors(source_path)
    sdl_file_names = set()
    for py_module_name in pfm_names:
        more_sdl_files, _ = find_sdl_depdendencies(sdl_mgrs, py_module_name)
        sdl_file_names.update(more_sdl_files)
    return tuple(sdl_file_names)

def find_pfm_dependency_pymodules(py_exe, source_path, pfm_names):
    module_names = set()
    for py_module_name in pfm_names:
        module_names.update(find_python_dependencies(py_exe, py_module_name, source_path))
    return tuple(module_names)

def find_python_dependencies(py_exe, module_name, scripts_path):
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
                    yield module_path
    else:
        if result.returncode == PyToolsResultCodes.traceback:
            logging.error(f"Python module {module_name} failed to import\n{result.stdout}.")
        elif result.returncode == PyToolsResultCodes.file_not_found:
            logging.warning(f"Python module {module_name} could not be found.")
        else:
            logging.warning(f"Unhandled error {result.returncode} when importing Python module {module_name}.\n{result.stdout}")

def find_sdl_depdendencies(sdl_mgrs, descriptor_name, embedded_sdr=False):
    dependencies = set()
    descriptors = set()

    for sdl_file, mgr in sdl_mgrs.items():
        descriptor = mgr.getDescriptor(descriptor_name)
        if descriptor is not None:
            break
    else:
        if embedded_sdr:
            logging.error(f"Embedded SDL Descriptor '{descriptor_name}' is missing from the client.")
        else:
            logging.debug(f"Python SDL '{descriptor_name}' is not present.")
        return dependencies, descriptors

    dependencies.add(sdl_file)
    descriptors.add(descriptor.name)

    # We need to see if there are any embedded state descriptor variables...
    for variable in descriptor.variables:
        if variable.type == plVarDescriptor.kStateDescriptor and not variable.stateDescType in descriptors:
            more_dependencies, more_descriptors = find_sdl_depdendencies(sdl_mgrs, variable.stateDescType, True)
            dependencies.update(more_dependencies)
            descriptors.update(more_descriptors)
    return dependencies, descriptors

def load_age(age_path):
    if not age_path.exists():
        logging.critical(f"Age file '{age_path}' does not exist.")
        return None

    age_info = plAgeInfo()
    try:
        age_info.readFromFile(age_path)
    except IOError as ex:
        logging.exception(ex)
        return False
    return age_info

def load_sdl_descriptors(sdl_path):
    sdl_mgrs = {}
    for sdl_file in sdl_path.glob("*.sdl"):
        # Strictly speaking, due to the configurable nature of the key, btea/notthedroids encrypted
        # SDL files are not allowed here. So, let's detect that.
        if plEncryptedStream.IsFileEncrypted(sdl_file):
            logging.error("SDL File '{sdl_file.name}' is encrypted and cannot be used for packaging.")
            continue

        mgr = plSDLMgr()
        mgr.readDescriptors(sdl_file)
        sdl_mgrs[sdl_file] = mgr
    return sdl_mgrs

def log_exception(ex):
    logging.exception(ex)

def make_asset_path(asset_category, *filename_pieces, **kwargs):
    subdir = client_subdirectories[asset_category]

    # If this is a Python or SDL file, we will allow usage of a specified moul-scripts repo...
    # We avoid doing this for .age, .fni, and .csv due to the un-WDYS'd nature of those files.
    if asset_category in {"python", "sdl"} and kwargs.get("scripts_path", None):
        return kwargs["scripts_path"].joinpath(subdir, *filename_pieces)
    else:
        return kwargs["client_path"].joinpath(subdir, *filename_pieces)

def output_package(output, outfile, client_path, scripts_path, subpackage_name=""):
    for asset_category, assets in output.items():
        src_subdir = client_subdirectories[asset_category]
        dest_subdir = asset_subdirectories[asset_category]
        for asset_filename, asset_dict in assets.items():
            asset_dict["source"] = str(pathlib.PureWindowsPath(dest_subdir, asset_filename))
            asset_source_path = make_asset_path(asset_category, asset_filename,
                                                client_path=client_path, scripts_path=scripts_path)
            asset_dest_path = pathlib.Path(subpackage_name, dest_subdir, asset_filename)
            outfile.copy_file(asset_source_path, asset_dest_path)

    outfile.write_file(pathlib.Path(subpackage_name, "Contents.yml"), dump(output, Dumper=Dumper))

def output_packages(all_outputs, client_path, scripts_path, destination_path):
    with _utils.OutputManager(destination_path) as outfile:
        # If we only have one package, we'll just toss that single package out into the destination
        if len(all_outputs) == 1:
            package_dict = all_outputs.get(next(iter(all_outputs)))
            logging.info("Writing package...")
            output_package(package_dict, outfile, client_path, scripts_path)
        else:
            for package_name, package_dict in all_outputs.items():
                logging.info(f"Writing subpackage '{package_name}'...")
                output_package(package_dict, outfile, client_path, scripts_path, package_name)

def prepare_packages(all_outputs, client_path, scripts_path, **kwargs):
    with multiprocessing.pool.Pool() as pool:
        missing_assets = []
        for package_name, package_dict in all_outputs.items():
            for asset_category, assets in package_dict.items():
                for asset_filename, asset_dict in assets.items():
                    asset_source_path = make_asset_path(asset_category, asset_filename,
                                                        client_path=client_path,
                                                        scripts_path=scripts_path)
                    if not asset_source_path.exists():
                        missing_assets.append((package_name, asset_category, asset_filename))
                        logging.warning(f"Asset '{asset_source_path.name}' (used in '{package_name}') is missing from the client.")
                        continue

                    # Fill in some information from the filesystem.
                    stat = asset_source_path.stat()
                    asset_dict["modify_time"] = int(stat.st_mtime)
                    asset_dict["size"] = stat.st_size

                    # Command line specs
                    for key, value in kwargs.items():
                        if value is not None:
                            asset_dict[key] = str(value)

                    # Now we submit slow operations to the process pool.
                    def pool_cb(asset_dict, key, value):
                        asset_dict[key] = value
                    md5_complete = functools.partial(pool_cb, asset_dict, "hash_md5")
                    sha2_complete = functools.partial(pool_cb, asset_dict, "hash_sha2")

                    pool.apply_async(_utils.hash_md5, (asset_source_path,),
                                     callback=md5_complete, error_callback=log_exception)
                    pool.apply_async(_utils.hash_sha2, (asset_source_path,),
                                     callback=sha2_complete, error_callback=log_exception)

        # Discard any missing thingos from our asset map and it will be very nearly final.
        for package_name, asset_category, asset_filename in missing_assets:
            all_outputs[package_name][asset_category].pop(asset_filename)
        for package_name in tuple(all_outputs.keys()):
            package_dict = all_outputs[package_name]
            for asset_category in tuple(package_dict.keys()):
                if not package_dict[asset_category]:
                    package_dict.pop(asset_category)
            if not package_dict:
                all_outputs.pop(package_name)

        # Wait for the pool to finish
        pool.close()
        pool.join()

        return not bool(missing_assets)

def main(args):
    if args.moul_scripts and not args.moul_scripts.exists():
        logging.error(f"Scripts path '{args.moul_scripts}' does not exist.")
        return False

    if args.age:
        age_info = load_age(make_asset_path("data", f"{args.age}.age", client_path=args.source))
        if age_info is None:
            return False
        age_infos = (age_info,)
    else:
        logging.info("Loading age files...")
        age_source_path = make_asset_path("data", client_path=args.source)
        age_infos = [load_age(age_file_path) for age_file_path in age_source_path.glob("*.age")]
        if not age_infos:
            logging.warning("No age files found in client!")
            return True
        elif not all(age_infos):
            return False

    # Collect a list of all age pages to be abused for the purpose of finding its resources
    # Would be nice if this were a common function of libHSPlasma...
    all_outputs = {}
    all_pages = [i for i in find_all_pages(all_outputs, make_asset_path("data", client_path=args.source), *age_infos)]
    logging.info(f"Found {len(all_pages)} Plasma pages.")

    # We want to get the age dependency data. Presently, those are the python and ogg files.
    # Unfortunately, libHSPlasma insists on reading in the entire page before allowing us to
    # do any of that. So, we will execute this part in a process pool.
    with multiprocessing.pool.Pool() as pool:
        dlevel = plDebug.kDLWarning if args.verbose else plDebug.kDLNone
        results = pool.starmap(find_page_externals, ((page_path, dlevel) for age_name, page_path in all_pages))

    # What we have now is a list of dicts, each nearly obeying the output format spec.
    # Now, we have to merge them... ugh.
    logging.info(f"Merging results from {len(results)} dependency lists...")
    coerce_asset_dicts(all_outputs, all_pages, results)

    # PythonFileMods can import other python modules and be a STATEDESC
    if not args.skip_pfm_dependencies:
        py_exe = args.python if args.python else _utils.find_python_exe()
        if not py_exe:
            logging.critical("Uru-compatible python interpreter unavailable.")
            return False
        logging.info("Searching for PythonFileMod dependencies...")
        find_pfm_externals(all_outputs, py_exe,
                           make_asset_path("python", client_path=args.source, scripts_path=args.moul_scripts),
                           make_asset_path("sdl", client_path=args.source, scripts_path=args.moul_scripts))

    # OK, now everything is (mostly) sane.
    logging.info("Beginning final pass over assets...")
    prepare_packages(all_outputs, args.source, args.moul_scripts, dataset=args.dataset, distribute=args.distribute)

    # Time to produce the bundle
    logging.info("Producing final asset bundle...")
    output_packages(all_outputs, args.source, args.moul_scripts, args.destination)

    return True
