# Update file EXIF date from file name

Most of the time, the file name of a photo contains the date and time when the photo was taken. This script reads the date and time from the file name and updates the EXIF date of the photo.

> This script is extremely conservative. Rather than messing up your photos, it will refuse to update the EXIF date.

The script boasts some hardcoded formats for the file name. If your file names don't match these formats, you can easily add your own.

The default run is a dry run. To actually update the EXIF date, you need to pass the `--wet_run True` flag.

Changes are applied atomically. If you cancel the script, no image will be broken. You may be left with an artifact temporary image.

## Installation

```bash
git clone https://github.com/nielstron/exif_from_filename.git
cd exif_from_filename 
pip install -r requirements.txt
```

## Usage

In order to see what changes _would_ be made, run the script with the default flags:

```bash
python exif_from_filename.py /path/to/photos
```

If you're happy with the changes, run the script with the `--wet_run True` flag:

```bash
python exif_from_filename.py /path/to/photos --wet_run True
```