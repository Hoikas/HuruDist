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
import pathlib
from PyHSPlasma import *

_BUFFER_SIZE = 10 * 1024 * 1024

def find_page_externals(path):
    # Optimization: Textures.prp does not have any externals...
    if path.name.endswith("Textures.prp"):
        return {}

    mgr = plResManager()
    page_info = mgr.ReadPage(str(path))
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
        "python": { f"{i.object.filename}.py": { "options": set(["pfm"]) }
                    for i in mgr.getKeys(location, pfm_idx) },

        "sfx": { i.object.fileName: { "options": set(sfx_flags_as_str(i.object.flags)) }
                 for i in mgr.getKeys(location, sfx_idx) },

        # OK, so, this is highly speculative... Don't die if they don't exist.
        "sdl": { f"{i.object.filename}.sdl": { "options": set(), "optional": True }
                 for i in mgr.getKeys(location, pfm_idx) },
    }

    # I know this isn't pretty, deal with it.
    if mgr.getKeys(location, plFactory.ClassIndex("plRelevanceRegion")):
        result["data"] = { f"{page_info.age}.csv": {} }

    return result


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
