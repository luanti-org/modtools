# `tr_po_converter.py`—Luanti Translation Format Converter

Since 5.10.0, Luanti has been able to support the standard gettext .po and
.mo translation file formats. These formats are highly recommended, as they
are much easier to manage via external tools such as Weblate, and also provide
more options for translators (such as correct plural forms).

## How it works
This script converts .txt/.tr files into .pot/.po ones.
It maintains comments but it ignores the `NOT USED ANYMORE` section.
Old .txt/.tr files are deleted, so be sure to make a backup first.

Optional argument `--test` runs automated tests to be sure that it works
correctly.

## How to use it
1. Drop the script in the root folder of a mod
2. Launch it
3. ..
4. Profit
