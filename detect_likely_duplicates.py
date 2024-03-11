import argparse
import json
import sys
import imagehash
import shutil
import time
import os
from typing import TypeAlias
from pathlib import Path
from mwclient import Site
from pathlib import Path
from PIL import Image, ImageFile, UnidentifiedImageError

ImageFile.LOAD_TRUNCATED_IMAGES = True

ImageHashes: TypeAlias = tuple[imagehash.ImageHash,
                               imagehash.ImageHash, imagehash.ImageHash]

CACHE_FILENAME = "cache.json"
DOWNLOAD_DIR = "download"
DUPLICATES_DIR = "duplicates"


def get_file_dir() -> Path:
    return Path(__file__).parent


def create_client(host) -> Site:
    return Site(host, path='/')


def ensure_directory(dir: str) -> None:
    loc = get_file_dir() / dir
    if not loc.exists():
        print("Creating " + str(loc))
        os.mkdir(loc)


def convert_mw_file_name(name: str) -> str:
    return name[len("FILE:"):]


def query_all_images(client: Site) -> list:
    print(f"Querying {client.host} images...")
    image_list = []
    for image in client.allimages():
        image_list.append(image)
    return image_list


def download_all_images(images: list):
    ensure_directory(DOWNLOAD_DIR)

    print("Downloading images...")
    for idx, image in enumerate(images):

        img_name = convert_mw_file_name(image.name)

        dl_path: Path = get_file_dir() / DOWNLOAD_DIR / img_name

        if not dl_path.exists():
            with open(dl_path, "wb") as outfile:
                image.download(outfile)
                print(
                    f"{idx + 1} / {len(images)} - [{image.imageinfo['size']} bytes] {img_name}")
                time.sleep(0.5)  # rate limit
        else:
            print(f"{idx + 1} / {len(images)} - [SKIPPED] {img_name}")


def download_mediawiki_images(host):
    client = create_client(host)
    all_images = query_all_images(client)
    download_all_images(all_images)


def hash_files(directory: Path, ignore_cache=False) -> tuple[list[str], dict[str, ImageHashes]]:
    files = os.listdir(directory)
    total = len(files)
    hashes: dict[str, ImageHashes] = {} if ignore_cache else load_cache()
    valid_files: list[str] = []
    original_cache_len = len(hashes.keys())

    print("Hashing data")
    for idx, filename in enumerate(files):
        if filename in hashes:
            print(f"[CACHED] {idx + 1} / {total}")
            valid_files.append(filename)
            continue
        try:
            img = Image.open(directory / filename)
            hashes[filename] = (imagehash.dhash_vertical(img, hash_size=64),
                                imagehash.dhash_vertical(img, hash_size=64),
                                imagehash.colorhash(img, binbits=3))
            valid_files.append(filename)
        except UnidentifiedImageError:
            print("Unknown File. ", end="")
        print(f"{idx + 1} / {total}")

    if not ignore_cache and len(hashes.keys()) != original_cache_len:
        save_cache(hashes)

    return valid_files, hashes


def detect_duplicates(filenames: list[str], hashes: dict[str, ImageHashes], distance, needle_filenames: list[str] | None = None, needle_hashes: dict[str, ImageHashes] | None = None) -> dict[str, list[str]]:
    total = len(needle_filenames or filenames)
    likely_duplicates: dict[str, list[str]] = {}

    needle_hashes = needle_hashes or hashes

    print("Detecting duplicates")
    seen_as_duplicate = set()
    for idx, x in enumerate(needle_filenames or filenames):
        other_files = filenames if needle_filenames else filenames[idx + 1:]
        for y in other_files:
            if not y in seen_as_duplicate and min(needle_hashes[x][0] - hashes[y][0], needle_hashes[x][1] - hashes[y][1]) <= distance and needle_hashes[x][2] - hashes[y][2] <= 2:
                likely_duplicates.setdefault(x, [x]).append(y)
                if not needle_filenames:
                    seen_as_duplicate.add(x)
                    seen_as_duplicate.add(y)
        print(f"{idx + 1} / {total}")

    return likely_duplicates


def copy_duplicates(src_path: Path, likely_duplicates: dict[str, list[str]], needle_path: Path | None = None):
    dupe_path = get_file_dir() / DUPLICATES_DIR
    if dupe_path.exists():
        shutil.rmtree(dupe_path)

    ensure_directory(DUPLICATES_DIR)
    print("Copying duplicates")

    for first_file_name, duplicate_names in likely_duplicates.items():
        os.mkdir(dupe_path / first_file_name)

        copy_from_idx = 0
        if needle_path:
            shutil.copy(needle_path / duplicate_names[0], dupe_path / first_file_name / duplicate_names[0])  # noqa
            copy_from_idx = 1

        for file_name in duplicate_names[copy_from_idx:]:
            shutil.copy(src_path / file_name, dupe_path / first_file_name / file_name)  # noqa


def detect_likely_duplicates(distance, needle: Path | None = None):
    base_path = get_file_dir() / DOWNLOAD_DIR

    if needle:
        if not base_path.exists():
            print("Mediawiki files not found. Download using URL as first argument.")
            exit()

        needle_files, needle_hashes = hash_files(needle, ignore_cache=True)
        haystack_files, haystack_hashes = hash_files(base_path)
        likely_duplicates = detect_duplicates(
            haystack_files, haystack_hashes, distance, needle_filenames=needle_files, needle_hashes=needle_hashes)
        copy_duplicates(base_path, likely_duplicates, needle_path=needle)

    else:
        files, hashes = hash_files(base_path)
        likely_duplicates = detect_duplicates(files, hashes, distance)
        copy_duplicates(base_path, likely_duplicates)


def save_cache(data: dict[str, ImageHashes]):
    file_path = get_file_dir() / CACHE_FILENAME
    data2 = {}
    for k, hashes in data.items():
        data2[k] = [str(h) for h in hashes]

    print("Saving image hashes.")
    with open(file_path, "w") as outfile:
        json.dump(data2, outfile)


def load_cache() -> dict[str, ImageHashes]:
    file_path = get_file_dir() / CACHE_FILENAME
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r") as infile:
            print("Loading cached image hashes.")
            data = json.load(infile)
            data2 = {}
            for k, hashes in data.items():
                data2[k] = [imagehash.hex_to_hash(hashes[0]), imagehash.hex_to_hash(
                    hashes[1]), imagehash.hex_to_flathash(hashes[2], hashsize=3)]

            return data2
    except Exception as e:
        print("Failed to load cache.", e)
        return {}


def free_cache():
    file_path = get_file_dir() / CACHE_FILENAME
    if file_path.exists():
        file_path.unlink()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            f"{Path(__file__).name} url_or_directory [distance (128)] [--dl-only] [--reset-cache]")
        exit()

    url_or_dir = sys.argv[1]
    distance = int(sys.argv[2]) if len(
        sys.argv) > 2 and sys.argv[2].isnumeric() else 128

    if "--reset-cache" in sys.argv[1:]:
        free_cache()

    check_path = get_file_dir() / url_or_dir

    if check_path.exists():
        detect_likely_duplicates(distance, needle=check_path)
    else:

        download_mediawiki_images(url_or_dir)
        if not "--dl-only" in sys.argv[1:]:
            detect_likely_duplicates(distance)
