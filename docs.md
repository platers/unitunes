# `unitunes`

Unitunes playlist manager

**Usage**:

```console
$ unitunes [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `add`: Add a playlist to the config file.
* `fetch`: Quickly add playlists from a service.
* `init`: Create a new playlist manager.
* `list`: List all playlists.
* `pull`: Pull playlist tracks from services.
* `push`: Push playlist tracks to services.
* `search`: Search for tracks on a service.
* `service`: Manage services
* `view`: Show a playlists metadata and tracks.

## `unitunes add`

Add a playlist to the config file.

If a playlist with the same name already exists, the url will be added to the playlist.
Otherwise, a new playlist will be created.

**Usage**:

```console
$ unitunes add [OPTIONS] NAME SERVICE_NAME [URL]
```

**Arguments**:

* `NAME`: [required]
* `SERVICE_NAME`: [required]
* `[URL]`

**Options**:

* `--help`: Show this message and exit.

## `unitunes fetch`

Quickly add playlists from a service.

**Usage**:

```console
$ unitunes fetch [OPTIONS] SERVICE_NAME
```

**Arguments**:

* `SERVICE_NAME`: [required]

**Options**:

* `-f, --force`: [default: False]
* `--help`: Show this message and exit.

## `unitunes init`

Create a new playlist manager.

**Usage**:

```console
$ unitunes init [OPTIONS] [DIRECTORY]
```

**Arguments**:

* `[DIRECTORY]`: Directory to store playlist files in  [default: .]

**Options**:

* `--help`: Show this message and exit.

## `unitunes list`

List all playlists.

**Usage**:

```console
$ unitunes list [OPTIONS]
```

**Options**:

* `--plain / --no-plain`: [default: False]
* `--help`: Show this message and exit.

## `unitunes pull`

Pull playlist tracks from services.

**Usage**:

```console
$ unitunes pull [OPTIONS] [PLAYLIST_NAMES]...
```

**Arguments**:

* `[PLAYLIST_NAMES]...`: Playlist names to pull from services

**Options**:

* `-s, --service TEXT`: Services to pull from
* `-v, --verbose`: [default: False]
* `--help`: Show this message and exit.

## `unitunes push`

Push playlist tracks to services.

**Usage**:

```console
$ unitunes push [OPTIONS] [PLAYLIST_NAMES]...
```

**Arguments**:

* `[PLAYLIST_NAMES]...`: Playlist names to push to services

**Options**:

* `-s, --service TEXT`: Service to push to
* `--help`: Show this message and exit.

## `unitunes search`

Search for tracks on a service.

If preview is set, URI's will not be added to the playlist.

**Usage**:

```console
$ unitunes search [OPTIONS] SERVICE:[spotify|ytm|mb] PLAYLIST
```

**Arguments**:

* `SERVICE:[spotify|ytm|mb]`: [required]
* `PLAYLIST`: [required]

**Options**:

* `--showall / --no-showall`: [default: False]
* `--debug / --no-debug`: [default: False]
* `--onlyfailed / --no-onlyfailed`: [default: False]
* `-p, --preview`: Preview tracks to add  [default: False]
* `--help`: Show this message and exit.

## `unitunes service`

Manage services

**Usage**:

```console
$ unitunes service [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `add`: Add a service.
* `list`: List all services.
* `playlists`: List all user playlists on a service.
* `remove`: Remove a service.

### `unitunes service add`

Add a service.

**Usage**:

```console
$ unitunes service add [OPTIONS] SERVICE:[spotify|ytm|mb] SERVICE_CONFIG_PATH [NAME]
```

**Arguments**:

* `SERVICE:[spotify|ytm|mb]`: [required]
* `SERVICE_CONFIG_PATH`: [required]
* `[NAME]`

**Options**:

* `--help`: Show this message and exit.

### `unitunes service list`

List all services.

**Usage**:

```console
$ unitunes service list [OPTIONS]
```

**Options**:

* `--plain / --no-plain`: [default: False]
* `--help`: Show this message and exit.

### `unitunes service playlists`

List all user playlists on a service.

**Usage**:

```console
$ unitunes service playlists [OPTIONS] SERVICE_NAME
```

**Arguments**:

* `SERVICE_NAME`: [required]

**Options**:

* `--help`: Show this message and exit.

### `unitunes service remove`

Remove a service.

**Usage**:

```console
$ unitunes service remove [OPTIONS] NAME
```

**Arguments**:

* `NAME`: [required]

**Options**:

* `-f, --force`: [default: False]
* `--help`: Show this message and exit.

## `unitunes view`

Show a playlists metadata and tracks.

**Usage**:

```console
$ unitunes view [OPTIONS] PLAYLIST
```

**Arguments**:

* `PLAYLIST`: [required]

**Options**:

* `--help`: Show this message and exit.
