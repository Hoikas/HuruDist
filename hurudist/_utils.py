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

import hashlib
import logging
import pathlib
import shutil
import subprocess
import sys
import zipfile

_BUFFER_SIZE = 10 * 1024 * 1024

def coerce_asset_dicts(dicts):
    """Forcibly merges asset dicts, preserving only options keys"""
    output = {}
    for dependency_categories in dicts:
        for dependency_category, dependencies in dependency_categories.items():
            if not dependency_category in output:
                output[dependency_category] = dependencies
            else:
                output_category = output[dependency_category]
                for dependency_name, dependency_dict in dependencies.items():
                    output_dict = output_category.setdefault(dependency_name, dependency_dict)
                    if "options" in output_dict:
                        new_options = set(output_dict["options"])
                        new_options.update(dependency_dict.get("options", []))
                        output_dict["options"] = list(new_options)
    return output

def find_python_exe(major=2, minor=7):
    def _find_python_reg(py_version):
        import winreg
        subkey_name = "Software\\Python\\PythonCore\\{}.{}\\InstallPath".format(*py_version)
        for reg_key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                python_dir = winreg.QueryValue(reg_key, subkey_name)
            except FileNotFoundError:
                continue
            else:
                return pathlib.Path(python_dir, "python.exe")
        return None

    # Maybe, someday, this will be true...
    if sys.version_info[:2] == (major, minor):
        return sys.executable

    # If we're on Windows, we can try looking in the registry...
    if sys.platform == "win32":
        py_exe = None
        for i in range(minor, 0, -1):
            py_exe = _find_python_reg((major, i))
            if py_exe:
                logging.debug(f"Found Python {major}.{i}: {py_exe}")
                return py_exe

    # Ok, now we try using some posix junk...
    args = ("command", "-v", f"python{major}.{minor}")
    result = subprocess.run(args, stdout=subprocess.PIPE, encoding="utf-8")
    if result.returncode == 0:
        logging.debug(f"Found Python {major}.{minor}: {result.stdout}")
        return result.stdout
    args = ("command", "-v", f"python{major}")
    result = subprocess.run(args, stdout=subprocess.PIPE, encoding="utf-8")
    if result.returncode == 0:
        logging.debug(f"Found Python {major}: {result.stdout}")
        return result.stdout

    # You win, I give up.
    logging.error(f"Could not find Python {major} interpreter.")
    return None

def find_python2_tools():
    tools_path = pathlib.Path(__file__).parent.joinpath("_py2tools.py")
    return tools_path

def _hash(path, hashobj):
    stat = path.stat()
    with open(path, "rb") as stream:
        if stat.st_size < _BUFFER_SIZE:
            hashobj.update(stream.read())
        else:
            buf = bytearray(_BUFFER_SIZE)
            while stream.readinto(buf):
                hashobj.update(buf)
    return hashobj.hexdigest()

def hash_md5(path):
    return _hash(path, hashlib.md5())

def hash_sha2(path):
    return _hash(path, hashlib.sha512())

class OutputManager:
    def __init__(self, path):
        self._is_zip = path.suffix == ".zip"
        self._path = path

        parent = path.parent
        if not parent.exists():
            parent.mkdir(parents=True)
        if self._is_zip:
            self._zip = zipfile.ZipFile(path, compression=zipfile.ZIP_DEFLATED, mode="w")

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self._is_zip:
            self._zip.close()
        return False

    def copy_file(self, source_path, dest_path):
        """Copies a file given by the absolute `source_path` to the relative `dest_path`."""
        if self._is_zip:
            self._zip.write(source_path, dest_path)
        else:
            dest_path = self._path / dest_path
            parent = dest_path.parent
            if not parent.exists():
                parent.mkdir(parents=True)
            shutil.copy2(source_path, dest_path)

    def write_file(self, path, data):
        if self._is_zip:
            self._zip.writestr(path, data)
        else:
            dest_path = self._path / path
            parent = dest_path.parent
            if not parent.exists():
                parent.mkdir(parents=True)
            dest_path.write_text(data)
