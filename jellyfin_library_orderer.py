# #############################################################################
# jellyfin_library_orderer.py
#
# DESCRIPTION
#
#   Sets the Home -> Library Order for every user on a Jellyfin server to a single order, as specified by the operator.
#
#   NOTE: this script will NOT modify any library access settings. If a library order is specified, the order will apply
#         to only the libraries that each user has access to.
#
# AUTHOR
#
#   https://github.com/anston-g
#
#   Inspiration taken from of Marc-Vieg's fork of Emby2Jelly (https://github.com/Marc-Vieg/Emby2Jelly)

# COMPATIBILITY
# 
#   Tested and confirmed to work with Jellyfin Server 12.0. Compatibility with alternate versions is not guaranteed.
#
# USAGE
#
#   python3 jellyfin_library_orderer.py
#   python3 jellyfin_library_orderer.py --dry-run
#
# On first run, if settings.ini does not exist, one is created for you to fill in and re-run.
# #############################################################################

import os
import json
import sys
import requests
from configobj import ConfigObj


CONFIG_PATH = "settings.ini"


def create_config(path):
    config = ConfigObj(path)
    config["Jelly"] = {
        "JELLY_APIKEY": "eeeeeeeeeeeeeeeffffffffffffffffggggggggg",
        "JELLY_URLBASE": "http://127.0.0.1:8096/",
    }
    config["Order"] = {
        # Comma-separated, in the exact order you want libraries to appear. Names must match your library names exactly (case-insensitive).
        # Any library NOT listed here keeps its current relative position for each user, appended after the ones that have a position listed.
        "LIBRARY_ORDER": "Movies, TV Shows, Music, Books",
        # Comma-separated usernames to skip (leave blank to apply the library ordering to everyone)
        "SKIP_USERS": "",
    }
    config.write()


def get_config(path):
    config = ConfigObj(path)
    apikey = config["Jelly"]["JELLY_APIKEY"]
    urlbase = config["Jelly"]["JELLY_URLBASE"]
    if not urlbase.endswith("/"):
        urlbase += "/"

    order_raw = config["Order"]["LIBRARY_ORDER"]
    if isinstance(order_raw, list):
        library_order = [n.strip() for n in order_raw if n.strip()]
    else:
        library_order = [n.strip() for n in order_raw.split(",") if n.strip()]

    skip_raw = config["Order"].get("SKIP_USERS", "")
    if isinstance(skip_raw, list):
        skip_users = {n.strip() for n in skip_raw if n.strip()}
    else:
        skip_users = {n.strip() for n in skip_raw.split(",") if n.strip()}

    return apikey, urlbase, library_order, skip_users


class JellyfinClient:
    def __init__(self, urlbase, apikey):
        self.urlbase = urlbase
        self.apikey = apikey
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-Emby-Token": apikey,
        }

    def get(self, path, params=None):
        params = dict(params or {})
        params["ApiKey"] = self.apikey
        r = requests.get(self.urlbase + path, headers=self.headers, params=params)
        r.raise_for_status() # raise a Python error if there is a HTTP error
        if r.content:
            return r.json()
        return None

    def post(self, path, params=None, body=None):
        params = dict(params or {})
        params["ApiKey"] = self.apikey
        r = requests.post(
            self.urlbase + path,
            headers=self.headers,
            params=params,
            data=json.dumps(body) if body is not None else None,
        )
        r.raise_for_status()
        return r


def get_library_name_to_id_dict(client):
    """
    Maps library display name to ItemId (GUID), using the virtual folders endpoint.
    in Dashboard -> Libraries.

    """
    folders = client.get("Library/VirtualFolders")
    name_to_id_dict = {}
    for folder in folders:
        name = folder.get("Name")
        item_id = folder.get("ItemId")
        if name and item_id:
            name_to_id_dict[name.lower()] = item_id
    return name_to_id_dict


def build_ordered_views(desired_names, name_to_id_dict, existing_ordered_views):
    """
    Builds the new OrderedViews list of GUIDs:
      1. GUIDs for names the operator specified, in that order.
      2. Any other library GUIDs that the current user has in their existing order.
      3. Finally, any other library GUIDs known to the server appended afterward.
    Avoids duplicates through all parts of the process.
    """
    new_order = []
    used_ids = set()

    unmatched_names = []
    for name in desired_names:
        item_id = name_to_id_dict.get(name.lower())
        if item_id is None:
            unmatched_names.append(name)
            continue
        if item_id not in used_ids:
            new_order.append(item_id)
            used_ids.add(item_id)

    # Preserve anything not explicitly ordered:

    # - first from the user's existing OrderedViews (if any)...
    for item_id in existing_ordered_views or []:
        if item_id not in used_ids:
            new_order.append(item_id)
            used_ids.add(item_id)

    # ...then any remaining library ids known to the server
    for item_id in name_to_id_dict.values():
        if item_id not in used_ids:
            new_order.append(item_id)
            used_ids.add(item_id)

    return new_order, unmatched_names


def set_library_order(dry_run=False):
    apikey, urlbase, library_order, skip_users = get_config(CONFIG_PATH)
    client = JellyfinClient(urlbase, apikey)

    print("Fetching libraries...")
    name_to_id_dict = get_library_name_to_id_dict(client)
    if not name_to_id_dict:
        print("No libraries found (check JELLY_URLBASE / JELLY_APIKEY). Aborting.")
        sys.exit(1)

    print(f"Found libraries: {', '.join(sorted(name_to_id_dict.keys()))}\n")

    print("Fetching users...")
    users = client.get("Users")
    print(f"Found {len(users)} users.\n")

    results = {"updated": [], "skipped": [], "failed": []}

    for user in users:
        username = user.get("Name")
        user_id = user.get("Id")

        if username in skip_users:
            print(f"Skipping {username} (in SKIP_USERS)")
            results["skipped"].append(username)
            continue

        configuration = user.get("Configuration", {}) or {}
        existing_ordered_views = configuration.get("OrderedViews", [])

        new_ordered_views, unmatched = build_ordered_views(
            library_order, name_to_id_dict, existing_ordered_views
        )

        if unmatched:
            print(
                f"\033[93mWarning: for user {username}, these names in LIBRARY_ORDER did not match any library and were ignored: {unmatched}\033[00m"
                )

        configuration["OrderedViews"] = new_ordered_views

        if dry_run:
            print(f"[DRY RUN] Would update {username} ({user_id}) -> OrderedViews: {new_ordered_views}")
            results["updated"].append(username)
            continue

        try:
            client.post(
                "Users/Configuration",
                params={"userId": user_id},
                body=configuration,
            )
            print(f"\033[92mUpdated library order for {username}\033[00m")
            results["updated"].append(username)
        except requests.exceptions.HTTPError as e:
            print(f"\033[91mFailed to update {username}: {e}\033[00m")
            results["failed"].append(username)

    print("\n\n--- Summary ---")
    print(f"Updated: {len(results['updated'])}")
    print(f"Skipped: {len(results['skipped'])}")
    print(f"Failed:  {len(results['failed'])}")

    if results["failed"]:
        print(f"Failed users: {', '.join(results['failed'])}")


if __name__ == "__main__":

    if not os.path.exists(CONFIG_PATH):
        create_config(CONFIG_PATH)
        print(
            f"Created {CONFIG_PATH}. Please edit it with your Jellyfin API key, URL, and "
            "desired LIBRARY_ORDER, then re-run this script."
        )
        sys.exit()

    dry_run = "--dry-run" in sys.argv
    set_library_order(dry_run=dry_run)
