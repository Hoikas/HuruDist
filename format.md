# H'uru Asset Tracking Format
This format is designed for the purpose of managing generated art assets, build artifacts, and dependencies for open source Uru shards in a flexible, readable format. This format was inspired by Chogon's [Gather Build JSON format](https://mystonline.com/forums/viewtopic.php?f=92&t=27719) but is designed to fix shortcomings of that format. Passing familiarity with the GatherBuild format is expected before continuing.

## Differences from Gather Build
The GatherBuild format is essentially a glorified list of files. The intention of the H'uru format is to utilize generally the same keys from the GatherBuild format but allow the storage of any arbitrary data such that the contents file store a true representation of the client for easy deployment to any server. In the interest of readability, the H'uru contents file will be serialized as YAML. Furthermore, in the interest of security, wildcards are forbidden.

Valid keys are as follows:
- `artifacts`
- `avi`
- `data`
- `python`
- `sdl`
- `sfx`

## H'uru Asset Map
The H'uru Asset Object replaces the string value from GatherBuild. Only the `source` key of the H'uru Asset Object is required. All other keys are optional. Each asset object is keyed by an asset filename that which represents the location of the file in the client. The following is a list of all meaningful keys and their anticipated values.

### Source
`source` represents the relative path from the content file to the data file. The value should not try to escape the working directory or be an absolute path.

`compressed_source` represents the relative path from the content file to a compressed copy of `source`. The same restrictions that apply to `source` apply to `compressed_source`.

## Compression
`compression` indicates either the desired compression type or the compression used by `compressed_source`. Valid options are:
- `gzip`
- `none`

**NOTE**: Not specifying this key gives the user the freedom to select their choice of compression options from the list of valid options.

## Hash
`hash_md5` respresents the MD5 hash of the file given by `source`. **WARNING**: The MD5 hash is known to be broken. This is included only for compatibility with the MOUL FileSrv protocol.

`hash_sha2` represents the SHA-2 512 hash of the file given by `source`.

`compressed_hash_md5` respresents the MD5 hash of the file given by `compressed_source`. **WARNING**: The MD5 hash is known to be broken. This is included only for compatibility with the MOUL FileSrv protocol.

`compressed_hash_sha2` represents the SHA-2 512 hash of the file given by `compressed_source`.

## Timestamp
`modify_time` represents the time since the unix epoch that `source` was last modified.

## Size
`size` represents the size of the file in bytes.

`compressed_size` represents the size of the file given by `compressed_source` in bytes.

## Data Set
`dataset` represents the dataset that the asset originates from. This enables asset scripts to properly handle asset collisions. A collision is defined as any assets whose client destination overlap and hashes do not match. Any collisions originating from the same `dataset` type is an error. Valid options are:
- `cyan` *A Cyan standard asset. **NOTE**: This value will cause `distribute` to default to `false`.*
- `base` *A baseline asset for the shard. Any collision with a `cyan` asset will cause this asset to be used.*
- `contrib` *A fan-contributed asset. A collision with any other asset will result in this asset being at best discarded.*
- `override` *Highest priority asset, overrides all other `dataset` options.*

## Distribute
`distribute` respresents the ability for the asset to be freely redistributed on an asset/file server. Valid options are:
- `true` - **DEFAULT** *Allow downloads of this asset.*
- `false` - *Do ***not*** allow downloads of this asset.*
- `always` - *Overrides any previous `false` values and allows the asset to be redistributed.*

## Options
`options` represents a list of string flags that are generally useful only to the client internally or to a file server. A generator should pass these flags along to any generated manifest. Valid options are:
- `sound_cache_split` - *only valid for objects in the `sfx` key*
- `sound_stream` - *only valid for objects in the `sfx` key*
- `sound_cache_stereo` - *only valid for objects in the `sfx` key*
- `redist` - *only valid for objects in the `artifacts` key*
- `pfm` - *only valid for objects in the `python` key*

## Optional
`optional` represents a build-time flag for whether or not it is permissible for a file to be missing. Valid options are:
- `true` - *The file may be omitted from the build without an error*
- `false` - **DEFAULT** *The file ***may not*** be omitted from the build*

## Build Type
`build_type` represents the client build type an `artifact` should be used in. This key is ignored outside of the `artifacts` key. Not specifying this key results in the asset being used for all build types. Valid options are:
- `external`
- `internal`

## Architecture
`arch` respresents the client build architecture. This key is ignored outside of the `artifacts` key. Not specifying this key results in the asset being used on all architectures. Valid options are:
- `amd64`
- `i386`

## Operating System
`os` represents the client operating system. This key is ignored outside of the `artifacts` key. Not specifying this key results in the asset being used on all operating systems. Valid options are:
- `mac`
- `win`
