"""Apply saved Animated Camos texture preferences between Black Ops sessions."""

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4
import zipfile

import menu_patch


PREFERENCES = ("master", "tvs", "box", "george", "traps")
PREFERENCE_LINE = re.compile(rb'^\s*seta\s+ac_visual_(' + b"|".join(name.encode() for name in PREFERENCES)
                             + rb')\s+"?([01])"?\s*$', re.I)
MENU = "zone/Common/code_post_gfx.ff"
TV = "zone/English/patch_ui.ff"
IWD = "main/iw_animatedcamos.iwd"
AUXILIARIES = ("zone/Common/mod.ff", "zone/Common/mp_animatedcamos.ff")
REQUIRED_STOCK = {MENU, "zone/Common/zombie_theater_patch.ff", "zone/Common/zombie_pentagon_patch.ff"}


def sha(path):
    if not path.is_file():
        return None
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def config_preferences(data):
    return {match[1].decode().lower(): match[2] == b"1" for row in data.splitlines()
            if (match := PREFERENCE_LINE.fullmatch(row))}


def seed_preferences(path, store):
    data = path.read_bytes() if path.is_file() else b""
    saved = config_preferences(data)
    missing = [name for name in PREFERENCES if name not in saved]
    if missing:
        assert_game_closed()
        if path.is_file():
            backup = store / "player-configs" / hashlib.sha256(os.fsencode(path)).hexdigest()[:24] / path.name
            if not backup.exists():
                replace(path, backup)
        newline = b"\r\n" if b"\r\n" in data or not data else b"\n"
        prefix = newline if data and not data.endswith(b"\n") else b""
        entries = [f'seta ac_visual_{name} "1"'.encode() for name in missing]
        write_atomic(path, data + prefix + newline.join(entries) + newline)
    return {**dict.fromkeys(PREFERENCES, True), **saved}


class ProcessEntry(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                ("executable", wintypes.WCHAR * wintypes.MAX_PATH)]


def game_running():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel.CreateToolhelp32Snapshot
    snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    snapshot.restype = wintypes.HANDLE
    first = kernel.Process32FirstW
    first.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    next_process = kernel.Process32NextW
    next_process.argtypes = first.argtypes
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    handle = snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ProcessEntry(size=ctypes.sizeof(ProcessEntry))
        found = first(handle, ctypes.byref(entry))
        while found:
            if entry.executable.casefold() in ("blackops.exe", "blackopsmp.exe"):
                return True
            found = next_process(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
        return False
    finally:
        close(handle)


def assert_game_closed():
    if game_running():
        raise ValueError("Close Black Ops before applying texture options.")


def replace(source, destination):
    if source is None:
        destination.unlink(missing_ok=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".animated-camos-", delete=False) as file:
        path = Path(file.name)
        try:
            with source.open("rb") as original:
                shutil.copyfileobj(original, file)
            file.close()
            os.replace(path, destination)
        finally:
            path.unlink(missing_ok=True)


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        pending = Path(file.name)
        try:
            file.write(data)
            file.close()
            os.replace(pending, path)
        finally:
            pending.unlink(missing_ok=True)


def json_atomic(path, value):
    write_atomic(path, json.dumps(value, indent=2).encode())


@contextmanager
def locked(store, name="lock", blocking=False):
    import msvcrt

    store.mkdir(parents=True, exist_ok=True)
    with (store / name).open("a+b") as file:
        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)


def recover(store, game):
    journal = store / "transaction.json"
    if not journal.exists():
        return
    recorded = json.loads(journal.read_text(encoding="utf-8"))
    current = json.loads((store / "state.json").read_text(encoding="utf-8"))["installed"]
    rows = recorded["files"]
    if not all(current[name] == row["after"] for name, row in rows.items()):
        for name, row in rows.items():
            if sha(game / name) not in (row["before"], row["after"]):
                raise ValueError(f"{name} changed during a prior interrupted update. Its rollback copy is under {store}.")
            before = store / "rollback" / name if row["before"] else None
            if before is not None and sha(before) != row["before"]:
                raise ValueError(f"rollback copy is missing or changed for {name}")
        for name, row in rows.items():
            replace(store / "rollback" / name if row["before"] else None, game / name)
    journal.unlink()


def apply_files(store, game, state, targets, preferences=None):
    assert_game_closed()
    recover(store, game)
    before = state["installed"]
    if set(before) != set(targets):
        raise ValueError("the profile does not match the installed overlay")
    for name, digest in before.items():
        if sha(game / name) != digest:
            raise ValueError(f"{name} was replaced outside Texture Options. Expected SHA-256 {digest}. "
                             f"Original and generated copies are under {store}.")
    after = {name: sha(path) if path is not None else None for name, path in targets.items()}
    if any(targets[name] is not None and digest is None for name, digest in after.items()):
        raise ValueError("a selected fastfile or IWD disappeared before installation")
    changes = {name: {"before": before[name], "after": digest} for name, digest in after.items()
               if before[name] != digest}
    updated = {**state, "installed": after}
    if preferences is not None:
        updated["applied_preferences"] = preferences
    if not changes:
        if updated != state:
            json_atomic(store / "state.json", updated)
        return
    for name, row in changes.items():
        if row["before"] is not None:
            replace(game / name, store / "rollback" / name)
    assert_game_closed()
    journal = store / "transaction.json"
    json_atomic(journal, {"files": changes})
    try:
        for name, row in changes.items():
            if sha(game / name) != row["before"]:
                raise ValueError(f"{name} changed while preparing the overlay")
            replace(targets[name], game / name)
            if sha(game / name) != row["after"]:
                raise ValueError(f"could not verify the installed file {name}")
        json_atomic(store / "state.json", updated)
    finally:
        recover(store, game)


def extract_checked(archive, members, target):
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.namelist()) != len(set(bundle.namelist())):
            raise ValueError(f"{archive} contains duplicate entries")
        for name, digest in members.items():
            selected = PurePosixPath(name)
            if selected.is_absolute() or ".." in selected.parts or ":" in name or "\\" in name:
                raise ValueError(f"invalid package member name {name}")
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(name) as source, path.open("wb") as dest:
                shutil.copyfileobj(source, dest)
            if sha(path) != digest:
                raise ValueError(f"wrong release file {name}")


def get_bundle():
    package = Path(__file__).with_name("texture-options.json")
    return json.loads(package.read_text(encoding="utf-8"))


def install_menu(store):
    stock = store / "stock" / MENU
    delta = Path(__file__).with_name("game-options.acpatch")
    write_atomic(store / "options/code_post_gfx.ff", menu_patch.apply_delta(stock.read_bytes(), delta.read_bytes()))


def setup(args, game, store, bundle):
    path = store / "state.json"
    if path.is_file():
        raise ValueError("Texture Options already manages this game. Restore it before setting up a different ZIP.")
    maps = bundle["layouts"][args.layout]
    stock = args.stock.resolve() if args.stock else game
    game_files = dict(bundle["stock"])
    originals = {name: sha(game / name) for name in game_files}
    stock_files = {name: sha(stock / name) for name in game_files}
    if stock_files[MENU] != game_files[MENU]:
        raise ValueError("Provide --stock with the original Steam code_post_gfx.ff and stock map patches.")
    for name, digest in game_files.items():
        if stock_files[name] != digest:
            base = name.removesuffix("_patch.ff") + ".ff"
            if (stock_files[name] is None and name not in REQUIRED_STOCK and name.endswith("_patch.ff")
                    and not (game / base).exists()):
                continue
            raise ValueError(f"Stock source mismatch for {name}. Use a clean Steam installation or a stock backup directory.")

    staged = store / "release"
    extract_checked(args.release.resolve(strict=True), maps["files"], staged)
    for name, digest in originals.items():
        if digest is not None:
            replace(game / name, store / "original" / name)
    for name, digest in stock_files.items():
        if digest is not None:
            replace(stock / name, store / "stock" / name)

    install_menu(store)
    state = {"layout": args.layout, "moon_fix": args.moon_fix, "originals": originals,
             "stock": stock_files, "installed": originals}
    json_atomic(path, state)
    return state


def map_sources(layout, moon_fix):
    for name, entry in layout["maps"].items():
        yield name, entry.get("alternate", entry["file"]) if moon_fix else entry["file"]


def map_variant(store, source, recipe):
    delta = Path(__file__).parent / recipe["path"]
    if sha(delta) != recipe["sha256"]:
        raise ValueError(f"the map patch differs from its checksum: {delta}")
    cache = store / "variants" / recipe["sha256"]
    if not cache.is_file():
        write_atomic(cache, menu_patch.apply_delta(source.read_bytes(), delta.read_bytes()))
    if hashlib.sha256(menu_patch.payload(cache.read_bytes())).hexdigest() != recipe["body_sha256"]:
        raise ValueError(f"the cached map variant failed verification: {source.name}")
    return cache


def profile_recipes(layout, name, source):
    previous = layout.get("previous_profiles", {}).get(name)
    if previous and sha(source) == previous["source_sha256"]:
        return previous["profiles"]
    return layout["profiles"][name]


def prepare_variants(bundle, state, store):
    layout = bundle["layouts"][state["layout"]]
    for _, source in map_sources(layout, state["moon_fix"]):
        base = store / "release" / source
        for recipe in profile_recipes(layout, source, base).values():
            map_variant(store, base, recipe)


def selected_targets(bundle, state, store, preferences):
    target = {name: store / "stock" / name if digest else None for name, digest in state["stock"].items()}
    target[MENU] = store / "options" / "code_post_gfx.ff"
    if preferences["master"]:
        layout = bundle["layouts"][state["layout"]]
        release = store / "release"
        target.update({name: release / name for name in (IWD, *AUXILIARIES)})
        if preferences["tvs"]:
            target[TV] = release / TV
        for name, source in map_sources(layout, state["moon_fix"]):
            base = release / source
            groups = profile_recipes(layout, source, base)
            disabled = "+".join(group for group in ("box", "george", "traps")
                                if group in groups and not preferences[group])
            target[name] = map_variant(store, base, groups[disabled]) if disabled else base
    for name, recipes in menu_patch.fov_maps().items():
        key = f"zone/Common/{name}"
        source = target[key]
        if source is not None:
            recipe = recipes.get(menu_patch.payload_hash(source.read_bytes()))
            if recipe is None:
                raise ValueError(f"The teleporter fix has no matching fastfile for {name}.")
            target[key] = map_variant(store, source, recipe)
    return target


def apply_profile(game, store, bundle, state, config):
    prefs = seed_preferences(config, store)
    apply_files(store, game, state, selected_targets(bundle, state, store, prefs), prefs)
    return prefs


def describe_preferences(preferences):
    return ", ".join(f"{name}={'On' if value else 'Off'}" for name, value in preferences.items())


def steam_install(game):
    steamapps = game.parent.parent
    manifest = steamapps / "appmanifest_42700.acf"
    if game.parent.name.casefold() != "common" or not manifest.is_file():
        return False
    match = re.search(r'^\s*"installdir"\s+"([^"\r\n]+)"', manifest.read_text(encoding="utf-8"), re.M)
    return match is not None and (steamapps / "common" / match[1]).resolve() == game


def steam_launch(game, executable):
    if not steam_install(game):
        raise ValueError("play needs the registered Steam install. Use apply to update a separate game copy.")
    steam = executable or Path(os.environ["ProgramFiles(x86)"]) / "Steam/Steam.exe"
    return steam.resolve(strict=True)


def shortcut_path(store):
    startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
    return startup / f"T5 Animated Camos {store.name}.lnk"


def monitor_settings(store):
    try:
        return json.loads((store / "monitor.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def register_monitor(game, store, bundle, config):
    token = uuid4().hex
    source = Path(__file__).resolve().parent
    helper = store / "helper" / token
    files = {"texture_options.py", "menu_patch.py", "texture-options.json", "game-options.acpatch"}
    files.update(recipe["path"] for layout in bundle["layouts"].values() for groups in layout["profiles"].values()
                 for recipe in groups.values())
    files.update(recipe["path"] for layout in bundle["layouts"].values()
                 for previous in layout.get("previous_profiles", {}).values()
                 for recipe in previous["profiles"].values())
    fov_maps = menu_patch.fov_maps()
    if fov_maps:
        files.add("fov-maps.json")
        files.update(recipe["path"] for recipes in fov_maps.values() for recipe in recipes.values())
    for name in files:
        replace(source / name, helper / name)
    python = Path(sys.executable).with_name("pythonw.exe").resolve(strict=True)
    arguments = ["-B", str(helper / "texture_options.py"), "--game", str(game), "watch", token]
    shortcut = shortcut_path(store)
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, T5_AC_SHORTCUT=str(shortcut), T5_AC_PYTHONW=str(python),
                       T5_AC_ARGUMENTS=subprocess.list2cmdline(arguments))
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                    "$link=(New-Object -ComObject WScript.Shell).CreateShortcut($env:T5_AC_SHORTCUT); "
                    "$link.TargetPath=$env:T5_AC_PYTHONW; $link.Arguments=$env:T5_AC_ARGUMENTS; $link.Save()"],
                   env=environment, check=True, capture_output=True, timeout=20,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    json_atomic(store / "monitor.json", {"token": token, "config": str(config)})
    subprocess.Popen([str(python), *arguments], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)


def monitor_log(store, message):
    with (store / "monitor.log").open("a", encoding="utf-8") as log:
        log.write(f"{datetime.now().astimezone().isoformat(timespec='seconds')} {message}\n")


def watch(game, store, bundle, token):
    with locked(store, "watch.lock", blocking=True):
        settings = monitor_settings(store)
        if settings.get("token") != token:
            return
        config = Path(settings["config"])
        state_path = store / "state.json"
        monitor_log(store, f"Watching {config} (PID {os.getpid()})")
        last_error = None
        while monitor_settings(store).get("token") == token and state_path.is_file():
            try:
                if not game_running():
                    saved = config_preferences(config.read_bytes()) if config.is_file() else {}
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    if saved != state.get("applied_preferences") or (store / "transaction.json").exists():
                        with locked(store):
                            if monitor_settings(store).get("token") != token or not state_path.is_file():
                                return
                            assert_game_closed()
                            recover(store, game)
                            state = json.loads(state_path.read_text(encoding="utf-8"))
                            prefs = apply_profile(game, store, bundle, state, config)
                            monitor_log(store, "Applied " + describe_preferences(prefs))
                    last_error = None
                time.sleep(0.5)
            except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
                if str(error) != last_error:
                    monitor_log(store, f"Waiting to apply preferences. {error}")
                    last_error = str(error)
                time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--config", type=Path, help="read preferences from a separate player config")
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("setup")
    install.add_argument("release", type=Path)
    install.add_argument("layout", choices=("normal", "goth", "stock"))
    install.add_argument("--stock", type=Path, help="directory containing verified stock game files")
    install.add_argument("--moon-fix", action="store_true")
    commands.add_parser("update", help="update an installed add-on while keeping its original backups")
    commands.add_parser("apply")
    play = commands.add_parser("play")
    play.add_argument("--steam", type=Path)
    commands.add_parser("restore")
    commands.add_parser("watch").add_argument("token")
    args = parser.parse_args()
    try:
        game = args.game.resolve(strict=True)
        if not (game / "BlackOps.exe").is_file():
            raise ValueError("the game directory must contain BlackOps.exe")
        steam = steam_launch(game, args.steam) if args.command == "play" else None
        key = hashlib.sha256(os.path.normcase(str(game)).encode()).hexdigest()[:24]
        store = Path(os.environ["LOCALAPPDATA"]) / "T5-Animated-Camos" / key
        bundle = get_bundle()
        if any(not (game / name).resolve().is_relative_to(game) for name in bundle["stock"]):
            raise ValueError("a managed file resolves outside the game directory")
        if args.command == "watch":
            watch(game, store, bundle, args.token)
            return
        assert_game_closed()
        with locked(store):
            state_path = store / "state.json"
            if args.command == "setup":
                state = setup(args, game, store, bundle)
            else:
                recover(store, game)
                state = json.loads(state_path.read_text(encoding="utf-8"))
            if args.command == "restore":
                original = {name: store / "original" / name if digest else None
                            for name, digest in state["originals"].items()}
                if any(sha(path) != state["originals"][name] for name, path in original.items() if path):
                    raise ValueError("an original rollback file is missing or changed")
                apply_files(store, game, state, original)
                state_path.unlink()
                if (store / "monitor.json").is_file():
                    (store / "monitor.json").unlink()
                    shortcut_path(store).unlink(missing_ok=True)
                print("Restored the files present before setup.")
                return
            if args.command == "update":
                install_menu(store)
            managed_steam = args.command in ("setup", "update") and steam_install(game)
            if managed_steam:
                print("Preparing stock texture variants for the selected layout.", flush=True)
                prepare_variants(bundle, state, store)
            watched_config = monitor_settings(store).get("config")
            config = (args.config or Path(watched_config or game / "players/config.cfg")).resolve()
            prefs = apply_profile(game, store, bundle, state, config)
            print("Texture Options applied. " + describe_preferences(prefs))
            if managed_steam:
                register_monitor(game, store, bundle, config)
                print("Texture Options will apply saved choices after Black Ops closes.")
            if steam is not None:
                arguments = [str(steam), "-applaunch", "42700"]
                for name, value in prefs.items():
                    arguments.extend(("+seta", f"ac_visual_{name}", str(int(value))))
                subprocess.Popen(arguments, cwd=steam.parent)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Texture Options failed. {error}\n")


if __name__ == "__main__":
    main()
