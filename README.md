# jellyfin-library-orderer

## ABOUT

Sets the Home -> Library Order for every user on a Jellyfin server to a single order, as specified by the operator.

NOTE: this script will NOT modify any library access settings. If a library order is specified, the order will apply to only the libraries that each user has access to.

## REQUIREMENTS

- Python 3.9+
- A Jellyfin API key (generate one in Jellyfin Dashboard -> API Keys)

Install dependencies:

```bash
pip install -r requirements.txt
```

## USAGE

```bash
python3 jellyfin_library_orderer.py
python3 jellyfin_library_orderer.py --dry-run
```

On first run, if settings.ini does not exist, one is created for you to fill in and re-run.

```ini
[Jelly]
JELLY_APIKEY = your-api-key-here
JELLY_URLBASE = http://127.0.0.1:8096/

[Order]
LIBRARY_ORDER = Movies, TV Shows, Music, Books
SKIP_USERS =
```

- `LIBRARY_ORDER`: comma-separated, in the order you want libraries to appear. Names must match your library names exactly (case-insensitive). Any library not listed keeps its current relative position, appended after the ones you do list.
- `SKIP_USERS`: comma-separated usernames to exclude (leave blank to apply to all users).

`--dry-run` previews the changes without writing to the server.

## COMPATIBILITY

Tested and confirmed to work with Jellyfin Server 12.0. Compatibility with alternate versions is not guaranteed.


## AUTHOR

https://github.com/anston-g

Inspiration taken from Marc-Vieg's fork of Emby2Jelly (https://github.com/Marc-Vieg/Emby2Jelly)


## LICENSE

MIT (see LICENSE)