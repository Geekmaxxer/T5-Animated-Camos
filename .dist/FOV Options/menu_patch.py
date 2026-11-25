"""Create or apply a delta for Black Ops' locally installed Game Options zone."""

import argparse
import csv
import hashlib
import io
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib


MAGIC = b"ACMENU30"
FASTFILE_HEADER = b"IWffu100\xd9\x01\x00\x00"
CHUNK = 64
MAX_PAYLOAD = 64 * 1024 * 1024
METADATA = struct.Struct("<8s32s32sI")
OPERATION = struct.Struct("<BI")


def payload(data):
    if not data.startswith(FASTFILE_HEADER):
        raise ValueError("expected a PC Black Ops fastfile")
    decoder = zlib.decompressobj()
    body = decoder.decompress(data[len(FASTFILE_HEADER):], MAX_PAYLOAD + 1)
    if not decoder.eof or len(body) > MAX_PAYLOAD:
        raise ValueError("invalid or oversized fastfile stream")
    return body


def create_delta(original, modified):
    old, new = map(payload, (original, modified))
    index = {old[pos:pos + CHUNK]: pos for pos in range(0, len(old) - CHUNK + 1, CHUNK)}
    operations = io.BytesIO()
    cursor = pending = 0
    while cursor <= len(new) - CHUNK:
        source = index.get(new[cursor:cursor + CHUNK])
        if source is None:
            cursor += 1
            continue
        if cursor > pending:
            operations.write(OPERATION.pack(0, cursor - pending))
            operations.write(new[pending:cursor])
        length = CHUNK
        while (source + length + CHUNK <= len(old) and cursor + length + CHUNK <= len(new)
               and old[source + length:source + length + CHUNK] == new[cursor + length:cursor + length + CHUNK]):
            length += CHUNK
        operations.write(OPERATION.pack(1, length))
        operations.write(struct.pack("<I", source))
        cursor += length
        pending = cursor
    if pending < len(new):
        operations.write(OPERATION.pack(0, len(new) - pending))
        operations.write(new[pending:])
    metadata = METADATA.pack(MAGIC, hashlib.sha256(original).digest(), hashlib.sha256(new).digest(), len(new))
    return metadata + zlib.compress(operations.getvalue(), level=9)


def apply_delta(original, delta):
    magic, expected_source, expected_body, size = METADATA.unpack_from(delta)
    if magic != MAGIC or not 0 < size <= MAX_PAYLOAD:
        raise ValueError("invalid Animated Camos menu patch")
    if hashlib.sha256(original).digest() != expected_source:
        raise ValueError("this patch needs the matching untouched Steam code_post_gfx.ff")
    old = payload(original)
    decoder = zlib.decompressobj()
    operations = io.BytesIO(decoder.decompress(delta[METADATA.size:], 2 * MAX_PAYLOAD))
    if not decoder.eof or decoder.unused_data:
        raise ValueError("invalid patch stream")
    rebuilt = bytearray()
    while header := operations.read(OPERATION.size):
        operation, length = OPERATION.unpack(header)
        if not 0 < length <= size - len(rebuilt):
            raise ValueError("invalid patch operation length")
        if operation == 0:
            block = operations.read(length)
        elif operation == 1:
            source, = struct.unpack("<I", operations.read(4))
            block = old[source:source + length]
        else:
            raise ValueError("unknown patch operation")
        if len(block) != length:
            raise ValueError("truncated patch operation")
        rebuilt.extend(block)
    if len(rebuilt) != size or hashlib.sha256(rebuilt).digest() != expected_body:
        raise ValueError("the reconstructed menu could not be verified")
    return FASTFILE_HEADER + zlib.compress(rebuilt)


def check_game_closed():
    result = subprocess.run(["tasklist.exe", "/FO", "CSV", "/NH"], text=True, errors="replace",
                            check=True, capture_output=True, timeout=15)
    if any(row and row[0].casefold() in {"blackops.exe", "blackopsmp.exe"}
           for row in csv.reader(result.stdout.splitlines())):
        raise ValueError("Close Black Ops before installing or restoring FOV Options.")


def write_zone(path, data, *, backup=False):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".fov-options-", delete=False) as file:
        pending = Path(file.name)
        try:
            file.write(data)
            file.close()
            if backup:
                os.rename(pending, path)
            else:
                os.replace(pending, path)
        finally:
            pending.unlink(missing_ok=True)


def manage_fov(game, restore):
    folder = Path(__file__).resolve().parent
    if (folder / "texture-options.json").exists():
        raise ValueError("Use texture_options.py to manage the Texture Options add-on.")
    game = game.resolve(strict=True)
    zone = game / "zone/Common/code_post_gfx.ff"
    backup = zone.with_suffix(".ff.acbackup")
    if not (game / "BlackOps.exe").is_file() or not zone.is_file():
        raise ValueError("Select your Black Ops installation folder.")
    check_game_closed()
    current = zone.read_bytes()
    has_backup = backup.exists()
    original = backup.read_bytes() if has_backup else current
    delta = (folder / "game-options.acpatch").read_bytes()
    patched = apply_delta(original, delta)
    if current != original and payload(current) != payload(patched):
        raise ValueError("The installed menu was changed by another patch. Restore it before using FOV Options.")
    if restore and not has_backup:
        raise ValueError(f"No FOV Options backup was found at {backup}")
    if not restore and not has_backup:
        write_zone(backup, original, backup=True)
    check_game_closed()
    if zone.read_bytes() != current:
        raise ValueError("The installed menu changed while preparing the patch.")
    write_zone(zone, original if restore else patched)
    print("Restored the stock Game Options menu." if restore else
          f"FOV Options installed. Original menu backed up to {backup}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("stock", type=Path)
    create.add_argument("candidate", type=Path)
    create.add_argument("output", type=Path)
    apply = commands.add_parser("apply")
    apply.add_argument("stock", type=Path)
    apply.add_argument("patch", type=Path)
    apply.add_argument("output", type=Path)
    commands.add_parser("install").add_argument("game", type=Path)
    commands.add_parser("restore").add_argument("game", type=Path)
    args = parser.parse_args()
    try:
        if args.command in ("install", "restore"):
            manage_fov(args.game, args.command == "restore")
            return
        source = args.stock.read_bytes()
        if args.command == "create":
            output = create_delta(source, args.candidate.read_bytes())
        else:
            output = apply_delta(source, args.patch.read_bytes())
        with args.output.open("xb") as file:
            file.write(output)
    except (OSError, ValueError, struct.error, subprocess.SubprocessError, zlib.error) as error:
        parser.exit(1, f"Menu patch failed. {error}\n")
    print(args.output)


if __name__ == "__main__":
    main()
