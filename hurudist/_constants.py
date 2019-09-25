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

import enum

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

class _ArgParseEnum:
    def __str__(self):
        return self.name

@enum.unique
class Dataset(_ArgParseEnum, enum.Enum):
    cyan = enum.auto()
    base = enum.auto()
    contrib = enum.auto()
    override = enum.auto()


@enum.unique
class Distribute(_ArgParseEnum, enum.Enum):
    # Purposefully hardcoding this value because Python enums begin with 1.
    false = 0
    true = enum.auto()
    # https://thedailywtf.com/articles/What_Is_Truth_0x3f_
    always = enum.auto()
