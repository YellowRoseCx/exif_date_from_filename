# Update file EXIF date from file name

Most of the time, the file name of a photo contains the date and time when the photo was taken. This script reads the date and time from the file name and updates the EXIF date of the photo.

> This script is extremely conservative. Rather than messing up your photos, it will refuse to update the EXIF date.

The script boasts some hardcoded formats for the file name. If your file names don't match these formats, you can easily add your own by modifying the config.yml.

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
python exif_date_from_filename.py /path/to/photos
```

If you're happy with the changes, run the script with the `--wet_run True` flag:

```bash
python exif_date_from_filename.py /path/to/photos --wet_run True
```

## Customization

The script comes with a default configuration file. If you want to add your own file name formats, you can do so by modifying the `config.yml` file.

```yaml
# filename_regex parsers are used to extract the date and time from the filename
- parser: filename_regex
  name: Custom IMG parser
  # example: IMG_20191209_043621
  regex: IMG_(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})_(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})\.*
# folder parsers are used to extract the date from any folder name in the path - use carefully as it updates contents in _all_ subfolders
- parser: folder
  folder_name: "Holiday0601"
  date: 2021-06-01
``` 

## Re-indexing (Nextcloud)

When using Nextcloud / Memories, you may want to re-index the photos after updating the EXIF date. This can be done by running the following command:

```bash
php occ memories:index --force --folder /path/to/photos
```

Because this command can take longer, exif_from_filename will print the folders that contain actual changes at the end of the run.