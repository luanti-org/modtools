# modtools
Useful tools for Luanti modding. Check the `doc` folder to learn more about the single tools.  

* `mod_translation_updater.py`: a script to automatically update `.tr` files.
  Deprecated, use `po_translation_updater.sh` if you're running Luanti 5.10.0+.
* `po_translation_updater.sh`: a script to automatically update `.po` files.
* `tr_po_converter.py`: a script to migrate old `.tr` files into the gettext standard `.po`
* `blockbench_to_minetest.sed`: `sed` script file to convert OBJ models produced by [Blockbench](https://www.blockbench.net/) to function correctly as Luanti node meshes
* `gltfutil.py`: a script to extract or strip embedded images in gltf files.
  run `./gltfutil.py -h` if you need help.
