# MediaWiki Image Duplicates
Python script to download and detect images which are likely duplicates of each other on a mediawiki website. The script can also check a local folder of images against the existing set of downloaded images.

## Installation
- Git clone or download the source code as a zip file and save to your PC, then unzip.

## Usage
- Create a python virtual environment (`python -m venv venv`)
- Activate the virtual environment (`venv\Scripts\activate.bat`)
- Run `pip install -r requirements.txt`
- To download and detect duplicates:
  - Run `detect_likely_duplicates.py` with the url to a mediawiki site.
- To check local folder against existing downloaded images:
  - Run `detect_likely_duplicates.py` with the name of a directory containing the new files

## Arguments
- --dl-only: only downloads files
- --reset-cache: deletes the cached hashes of the files
