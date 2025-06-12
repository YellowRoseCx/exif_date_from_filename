#!/usr/bin/env python3
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import List

from PIL import Image
import piexif
import fire
from tqdm import tqdm
import yaml

_LOGGER = logging.getLogger(__name__)

VERSION = "0.1.0"
PROCESSED_TAG_INDEX = 0xfe69
assert PROCESSED_TAG_INDEX not in piexif.ExifIFD.__dict__.values()
piexif.TAGS["Exif"][PROCESSED_TAG_INDEX] = {"name": "ExifDateFromFilename", "type":piexif.TYPES.Undefined}
PROCESSED_TAG_NON_VARIABLE = "exif_date_from_filename"
PROCESSED_TAG = f"{PROCESSED_TAG_NON_VARIABLE}_v{VERSION}"


class Parser:
    def parse_date(self, filename: Path):
        raise NotImplementedError()

@dataclass
class RegexNameParser(Parser):
    """
    A class to parse date from filename using regex pattern
    The regex pattern should have named groups for year, month, day, hour, minute, second (last 3 are optional)
    """
    name: str
    regex: re.Pattern

    @staticmethod
    def from_config(config: dict):
        return RegexNameParser(config["name"], re.compile(config["regex"]))

    def parse_date(self, filename: Path):
        _LOGGER.debug(f"Trying {self.name} filename parser")
        date_str = filename.stem
        match = self.regex.match(date_str)
        if not match:
            return None
        groupdict = match.groupdict()
        try:
            # Parse the date string
            date_obj = datetime(
                int(groupdict["year"]),
                int(groupdict["month"]),
                int(groupdict["day"]),
                int(groupdict.get("hour", 0)),
                int(groupdict.get("minute", 0)),
                int(groupdict.get("second", 0)),
            )
            return date_obj
        except ValueError:
            return None


@dataclass
class FolderNameParser(Parser):
    """
    A class to assign a fixed date to all images in a folder
    """
    folder_name: str
    date: datetime

    @staticmethod
    def from_config(config: dict):
        return FolderNameParser(config["folder_name"], config["date"])

    def parse_date(self, filename: Path):
        _LOGGER.debug(f"Trying {self.folder_name} folder name parser")
        if self.folder_name in filename.parts:
            return self.date


def parse_date_from_filename(parsers: List[Parser], filename: Path):
    for parser in parsers:
        date = parser.parse_date(filename)
        if date:
            return date
    return None


def update_exif_date(parsers: List[Parser], image_path: Path, dry_run: bool = False, update: bool = False, force: bool = False) -> bool:
    # Parse date from filename (assumed to be faster than actually opening the image)
    date_taken = parse_date_from_filename(parsers, image_path)
    if not date_taken:
        _LOGGER.debug(f"Could not parse date from filename: {image_path}")
        return False
    if dry_run:
        _LOGGER.info(f"Would update EXIF date for {image_path} to {date_taken}")
        return False
    # Open the image
    try:
        img = Image.open(image_path)
    except Exception as e:
        _LOGGER.debug(f"Error opening {image_path}: {str(e)}")
        if "cannot identify image file" in str(e):
            _LOGGER.debug(f"Skipping non-image file: {image_path}")
        else:
            _LOGGER.warning(f"Error opening {image_path}: {str(e)}")
        return False
    try:

        # Check if EXIF data exists
        if "exif" in img.info:
            exif_dict = piexif.load(img.info["exif"])
        else:
            exif_dict = {"0th": {}, "1st": {}, "Exif": {}, "GPS": {}, "Interop": {}}

        # Check if DateTimeOriginal tag is already set
        # and was written by us
        if piexif.ExifIFD.DateTimeOriginal not in exif_dict["Exif"] or (
           exif_dict["Exif"].get(PROCESSED_TAG_INDEX, b"").decode("ascii").startswith(PROCESSED_TAG_NON_VARIABLE) and update
        ) or force:
            _LOGGER.debug(f"Writing EXIF date")

            # Set the DateTimeOriginal tag
            date_taken_fmt = date_taken.strftime("%Y:%m:%d %H:%M:%S")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_taken_fmt.encode(
                "utf-8"
            )
            # Add processed tag
            exif_dict["Exif"][PROCESSED_TAG_INDEX] = PROCESSED_TAG.encode("ascii")

            # Save the updated EXIF data (atomic, to avoid corrupting the image)
            exif_bytes = piexif.dump(exif_dict)
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=image_path.suffix, dir=image_path.parent
            ) as tmp:
                img.save(tmp.name, exif=exif_bytes)
            
            # Close the image before replacing the file
            img.close()
            
            # On Windows, file handles might not be released immediately
            # Try multiple times with increasing delays
            max_retries = 3
            for retry in range(max_retries):
                try:
                    os.replace(tmp.name, image_path)
                    break  # Success, exit the retry loop
                except PermissionError as e:
                    if retry < max_retries - 1:
                        # Exponential backoff: 0.1s, 0.2s, 0.4s
                        import time
                        time.sleep(0.1 * (2 ** retry))
                        continue
                    else:
                        # All retries failed
                        _LOGGER.warning(f"Failed to replace file after {max_retries} retries: {str(e)}")
                except Exception as e:
                    _LOGGER.warning(f"Unexpected error replacing file: {str(e)}")
                finally:
                    try:
                        os.remove(tmp.name)  # Clean up the temporary file
                    except Exception:
                        pass  # Ignore errors when cleaning up
            _LOGGER.info(f"Updated EXIF date for {image_path} to {date_taken}")
            return True
        else:
            _LOGGER.debug(f"EXIF date already set for {image_path}")

    except Exception as e:
        _LOGGER.warning(f"Error processing {image_path}: {str(e)}", exc_info=e)
    return False

PARSER_CLASSES = {
    "filename_regex": RegexNameParser,
    "folder": FolderNameParser,
}

def load_config(config:str):
    with open(config, "r") as ymlfile:
        cfg = yaml.safe_load(ymlfile)
    parsers = []
    for entry in cfg:
        parser_class = PARSER_CLASSES[entry["parser"]].from_config(entry)
        parsers.append(parser_class)
    return parsers


def process_directory(
    directory: str, verbosity: int = logging.INFO, config:str = "./config.yml", wet_run: bool = False, update: bool= False, force: bool = False
):
    """
    Process all images in the given directory and update their EXIF date based on filename, if missing
    :param directory: Directory containing images
    :param verbosity: Logging verbosity level
    :param wet_run: Perform the actual update (default is dry run)
    :param update: Overwrite tags that were written by us
    :param force: Force update even if DateTimeOriginal tag is already set by external software
    :param config: Path to the config file
    """
    # cursed logging setup
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(verbosity)
    _LOGGER.setLevel(verbosity)
    _LOGGER.addHandler(handler)

    parsers = load_config(config)

    # actual processing
    # Use os.walk instead of Path.walk() for Python 3.11 compatibility
    dir_path_obj = Path(directory)
    walk_iter = os.walk(dir_path_obj)
    if verbosity > logging.INFO:
        # should add a progress bar if verbosity is high
        walk_iter = tqdm(list(walk_iter))
    updated_dirs = set()
    for root, dir_names, file_names in walk_iter:
        dir_path = Path(root)
        _LOGGER.info(f"Processing directory: {dir_path}")
        for filename in sorted(file_names):
            if Path(filename).suffix.lower() not in [
                ".jpg",
                ".jpeg",
                ".tif",
                ".webp",
                ".tiff",
                ".png",
            ]:
                continue
            _LOGGER.debug(f"Processing file: {filename}")
            image_path = dir_path / filename
            updated = update_exif_date(parsers, image_path, not wet_run, update, force)
            if updated:
                updated_dirs.add(dir_path)
    _LOGGER.info("Done!")
    if updated_dirs:
        _LOGGER.info("Dumping updated directories to stdout")
        for dir in updated_dirs:
            print(dir)
    else:
        _LOGGER.info("No directories were updated.")


# Usage
if __name__ == "__main__":
    fire.Fire(process_directory)
