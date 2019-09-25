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

import shutil
import zipfile

client_subdirectories = {
    "artifacts": "",
    "avi": "avi",
    "data": "dat",
    "python": "Python",
    "sdl": "SDL",
    "sfx": "sfx",
}

asset_subdirectories = {
    "artifacts": "Client",
    "avi": "GameVideos",
    "data": "GameData",
    "python": "GameScripts",
    "sdl": "GameState",
    "sfx": "GameAudio",
}

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
