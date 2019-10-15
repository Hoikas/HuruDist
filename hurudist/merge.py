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

from ruamel.yaml import YAML

from _constants import *
import copy
import functools
import logging
from pathlib import Path
import _utils

class MalformedPackageError(Exception):
    def __init__(self, path, msg):
        super().__init__(f"Package '{path}' {msg}")


class PackageSanityError(Exception):
    pass


def load_asset_db(source_path):
    """Loads the asset database given by source path as a dict, mapping (asset_category, asset_filename)
       to a dict containing a set of subpackage names and asset dicts. NOTE: this is a destructive
       operation and will not return the data as-is on disk.
    """
    database = {}
    yaml = YAML()
    logging.info(f"Loading asset database '{source_path}'...")
    _load_package(source_path, "contents.yml", yaml, database)
    # fixme: need to go through and validate hashes, zips???
    return database

def _load_package(base_path, source_path, yaml, database, subpackage_name=None):
    yaml_path = base_path.joinpath(source_path)
    logging.info(f"Loading package '{source_path}'...")
    bundle = yaml.load(yaml_path)
    subpackages = bundle.pop("subpackages", [])
    if subpackages and bundle:
        logging.warning(f"Package '{source_path}' has subpackages and assets. This is nonstandard and may not work.")

    for i in subpackages:
        subpackage_name = i.get("name", None)
        if not subpackage_name:
            raise MalformedPackageError(source_path, "has an unnamed subpackage.")
        subpackage_path = i.get("source", None)
        if not subpackage_path:
            raise MalformedPackageError(source_path, f"has a subpackage named '{subpackage_name}' without a source path.")
        _load_package(base_path, subpackage_path, yaml, database, subpackage_name)

    # Map this out into an easy to consume way...
    relative_path = yaml_path.parent.relative_to(base_path)
    for asset_category, assets in bundle.items():
        asset_category = asset_category.lower()
        for asset_filename, asset_dict in assets.items():
            asset_map = database.setdefault((asset_category, asset_filename.lower()), { "filename": asset_filename })
            if subpackage_name is not None:
                asset_map.setdefault("subpackages", set()).add(subpackage_name)

            # Fixup the source paths to be relative from the database directory.
            if "source" not in asset_dict:
                raise MalformedPackageError(source_path, f"has an asset ('{asset_category}', '{asset_filename}') without a source")
            asset_dict["source"] = _utils.win_path_str(relative_path, asset_dict["source"])
            if "compressed_source" in asset_dict:
                asset_dict["compressed_source"] = _utils.win_path_str(relative_path, asset_dict["compressed_source"])

            asset_map.setdefault("dicts", []).append(asset_dict)

def reduce_db(database):
    """Merges a flat asset database in the format used by `load_asset_db()`"""
    def _find_priority_asset(value, element):
        if value is None:
            return element

        def _sanity_check(key):
            if key not in value or key not in element:
                return False
            if value[key] == element[key]:
                return True
            raise PackageSanityError()

        value_dataset = Dataset[value.get("dataset", "base").lower()]
        element_dataset = Dataset[element.get("dataset", "base").lower()]
        if value_dataset == element_dataset:
            # Tries any of the listed keys to ensure the assets are equivalent. If none are available,
            # that is a failure to sanity check.
            if not any(map(_sanity_check, ("size", "hash_sha2", "hash_md5"))):
                raise PackageSanityError()
            return value
        elif value_dataset < element_dataset:
            return element
        else:
            return value

    nuke = []
    logging.info("Reducing database...")
    for (asset_category, asset_filename), asset_map in database.items():
        try:
            final_asset = functools.reduce(_find_priority_asset, asset_map["dicts"])
        except PackageSanityError:
            logging.error(f"Asset ('{asset_category}', '{asset_filename}') has conflicts. Discarding.")
            nuke.append((asset_category, asset_filename))
        else:
            # Even though we have the "final" version, we need to merge in the options to ensure
            # nothing gets lost from the other copies of this asset.
            _utils.merge_options(final_asset, asset_map["dicts"])
            asset_map["asset"] = final_asset
    for i in nuke:
        del database[i]

def save_db(database, source_path, dest_path, preserve_subpackages=False):
    def copy_asset(key):
        asset_source_path = source_path.joinpath(asset_map["asset"][key])
        asset_dest_path = dest_path.joinpath(asset_subdirectories[asset_category], asset_map["filename"])
        logging.debug(f"Copying '{asset_source_path}' to '{asset_dest_path}'")
        outfile.copy_file(asset_source_path, asset_dest_path)
        asset_map["asset"][key] = _utils.win_path_str(asset_subdirectories[asset_category], asset_map["filename"])

    with _utils.OutputManager(dest_path) as outfile:
        all_outputs = {}
        logging.info("Copying assets...")
        for (asset_category, asset_filename), asset_map in database.items():
            if "asset" not in asset_map:
                logging.error(f"Asset ('{asset_category}', '{asset_filename}') needs to be reduced!")
                continue

            copy_asset("source")
            if "compressed_source" in asset_map["asset"]:
                copy_asset("compressed_source")

            if preserve_subpackages:
                subpackages = (all_outputs.setdefault(i, {}) for i in asset["subpackages"])
            else:
                subpackages = [all_outputs,]
            for subpackage in subpackages:
                output_category = subpackage.setdefault(asset_category, {})
                output_category[asset_map["filename"]] = asset_map["asset"]

        yaml = YAML()
        if preserve_subpackages:
            subpackages = [{ "name": subpackage_name, "source": f"{subpackage_name}.yml" }
                           for subpackage_name in all_outputs.keys()]
            logging.info("Writing subpackage YAML...")
            for subpackage in subpackages:
                yaml.dump(all_outputs[subpackage["name"]], outfile.open_file(subpackage["source"], "w"))
                all_outputs.pop(subpackage["name"])
            all_outputs["subpackages"] = subpackages
        logging.info("Writing package YAML...")
        yaml.dump(all_outputs, outfile.open("contents.yml", "w"))

def main(args):
    source_path = args.source
    if not source_path.exists():
        logging.error(f"Source path '{source_path}' does not exist.")
        return False
    if not source_path.is_dir():
        logging.error(f"Source path '{source_path}' must be a directory.")
        return False

    database = load_asset_db(source_path)
    reduce_db(database)
    save_db(database, source_path, args.destination)

    return True
