import logging
import os
from pathlib import Path
from datetime import datetime
from PIL import Image
import piexif
import fire
from tqdm import tqdm

_LOGGER = logging.getLogger(__name__)

def parse_date_iOS_filename(filename: Path):
    _LOGGER.debug(f"Trying iOS filename parser")
    # Extract date and time from filename on iPhone (old)
    # Check that file ends with .jpg or .jpeg
    if filename.suffix.lower() not in ['.jpg', '.jpeg']:
        return None
    date_str = filename.stem
    try:
        # Parse the date string
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H.%M.%S')
        return date_obj.strftime("%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None



FILENAME_PARSERS = [
    parse_date_iOS_filename,
]

def parse_date_from_filename(filename: Path):
    for parser in FILENAME_PARSERS:
        date = parser(filename)
        if date:
            return date
    return None


def update_exif_date(image_path: Path, dry_run: bool = False):
    # Parse date from filename (assumed to be faster than actually opening the image)
    date_taken = parse_date_from_filename(image_path)
    if not date_taken:
        _LOGGER.debug(f"Could not parse date from filename: {image_path}")
        return
    # Open the image
    try:
        img = Image.open(image_path)
    except Exception as e:
        _LOGGER.debug(f"Error opening {image_path}: {str(e)}")
        if "cannot identify image file" in str(e):
            _LOGGER.debug(f"Skipping non-image file: {image_path}")
        else:
            _LOGGER.warning(f"Error opening {image_path}: {str(e)}")
        return
    try:

        # Check if EXIF data exists
        if 'exif' in img.info:
            exif_dict = piexif.load(img.info['exif'])
        else:
            exif_dict = {'0th': {}, '1st': {}, 'Exif': {}, 'GPS': {}, 'Interop': {}}

        # Check if DateTimeOriginal tag is already set
        if piexif.ExifIFD.DateTimeOriginal not in exif_dict['Exif']:

            # Set the DateTimeOriginal tag
            exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = date_taken.encode('utf-8')

            # Save the updated EXIF data
            exif_bytes = piexif.dump(exif_dict)
            if not dry_run:
                img.save(image_path, exif=exif_bytes)
            _LOGGER.info(f"Updated EXIF date for {image_path} to {date_taken}")
        else:
            _LOGGER.debug(f"EXIF date already set for {image_path}")

    except Exception as e:
        _LOGGER.warning(f"Error processing {image_path}: {str(e)}")


def process_directory(directory: str, verbosity: int = logging.INFO, wet_run: bool = False):
    """
    Process all images in the given directory and update their EXIF date based on filename, if missing
    :param directory: Directory containing images
    :param verbosity: Logging verbosity level
    :param wet_run: Perform the actual update (default is dry run)
    """
    # cursed logging setup
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(verbosity)
    _LOGGER.setLevel(verbosity)
    _LOGGER.addHandler(handler)

    # actual processing
    for dir_path, dir_names, file_names in tqdm(Path(directory).walk()):
        _LOGGER.info(f"Processing directory: {dir_path}")
        for filename in file_names:
            _LOGGER.debug(f"Processing file: {filename}")
            image_path = dir_path / filename
            update_exif_date(image_path, not wet_run)


# Usage
if __name__ == "__main__":
    fire.Fire(process_directory)