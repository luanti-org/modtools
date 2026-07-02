# `po_translation_updater.py`—Luanti Mod Translation Updater

This bash script is intended to easily update `.pot/.po` files, coming with
a few utilities to make developers life easier.

### Defining the helper functions

In any source code file with translatable strings, you have to manually define helper
functions at the top with something like `local S = core.get_translator("<textdomain>")`.
Optionally, you can also define additional helper functions `FS`, `NS` and `NFS` if needed.

Here is the list of all recognized function names. All functions return a string.

* `S`: Returns translation of input. See Luanti's `lua_api.md`. You should always have at
       least this function defined.
* `PS`: Same as `S`, but it takes the plural form of the string as 2nd argument.
* `NS`: Returns the input. Useful to make a string visible to the script without actually
        translating it here.
* `FS`: Same as `S`, but returns a formspec-escaped version of the translation of the input.
        Supported for convenience.
* `FPS`: Same as `FS`, but it takes the plural form of the string as 2nd argument.
* `NFS`: Returns a formspec-escaped version of the input, but not translated.
         Supported for convenience.

Template boilerplate for mods. Copy what you need:

    local S = core.get_translator("<textdomain>")
    local S, PS = core.get_translator("<textdomain>")
    local NS = function(s) return s end
    local FS = function(...) return core.formspec_escape(S(...)) end
    local FPS = function(...) return core.formspec_escape(PS(...)) end
    local NFS = function(s) return core.formspec_escape(s) end
    
### A minimal example

This minimal code example sends "Hello world!" to a player when they log in,
translated according to the language of their client:

    local S = core.get_translator("example")
    core.register_on_joinplayer(function(player)
        core.chat_send_player(player:get_player_name(), S("Hello world!"))
    end)
    
### Leaving notes for translators

If you want to leave some notes for translators, put a comment on top of the needed string
starting with `S-NOTE:`. Example:

```lua
-- S-NOTE: The translated version must not be longer than 6 characters
core.chat_send_all("Hello!")
```

It also supports new lines, e.g.

```lua
-- S-NOTE: This is a very long comment, because I have to explain you
-- a lot of different things regarding the string that follows...
core.chat_send_all("Foo bar")
```

Translations are automatically propagated from `.pot` files into `.po` ones.

### How to use it
1. Drop the script in the root folder of a mod
2. Run it through python
3. ..
4. Profit

### Command-line Parameters
* `-s`, `--skip-po`: skips the update of .po files
* `--test`: runs automated tests
