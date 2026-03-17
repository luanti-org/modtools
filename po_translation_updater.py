# CC0
# po_translation_updater.py — Luanti xgettext helper
#
# Extracts translatable strings from .lua files using xgettext, strips
# the S-NOTE prefix from extracted translator comments, and updates
# existing .po files via msgmerge.

import argparse
import contextlib
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import shutil
import tempfile
import unittest


LOCALE_DIR_DEFAULT = "locale"
SNOTE_PATTERN = re.compile(r"^#\. S-NOTE: ")
SNOTE_REPLACEMENT = "#. "

XGETTEXT_KEYWORDS = [
    "--keyword=S",
    "--keyword=PS:1,2",
    "--keyword=NS",
    "--keyword=FS",
    "--keyword=FPS:1,2",
    "--keyword=NFS",
]


# ====================================================================
# CORE FUNCTIONS
# ====================================================================


def find_lua_files(root: str) -> list[str]:
    """Find all .lua files under *root*, excluding .git directories."""
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for fn in filenames:
            if fn.endswith(".lua"):
                result.append(os.path.join(dirpath, fn))
    result.sort()
    return result

def normalize_printed_paths(file: str) -> None:
    pattern = re.compile(r'^(#:\s*)(.+)', flags=re.MULTILINE)
    path = Path(file)
    content = path.read_text(encoding="utf-8")

    def replacer(match):
        prefix = match.group(1)
        rest = match.group(2)

        rest = rest.replace("\\", "/")
        rest = re.sub(r'^\.\/', '', rest)

        return prefix + rest

    content = pattern.sub(replacer, content)
    path.write_text(content, encoding="utf-8", newline="\n")


def strip_snote_prefix(pot_path: Path) -> None:
    """
    Strip the 'S-NOTE: ' prefix from comment lines in a .pot file.

    Transforms:
        #. S-NOTE: text   ->  #. text

    """
    text = pot_path.read_text(encoding="utf-8")
    lines = [SNOTE_PATTERN.sub(SNOTE_REPLACEMENT, line) for line in text.split("\n")]
    pot_path.write_text("\n".join(lines), encoding="utf-8")


def run_xgettext(lua_files: list[str], pot_path: Path, *, quiet: bool = False) -> None:
    cmd = [
        "xgettext",
        "--language=Lua",
        "--from-code=UTF-8",
        "--add-comments=S-NOTE",
        *XGETTEXT_KEYWORDS,
        f"--output={pot_path}",
        *lua_files,
    ]
    run_kwargs = {"check": True}
    if quiet:
        run_kwargs.update({"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True})
    subprocess.run(cmd, **run_kwargs)

    if sys.platform.startswith("win"): # always use POSIX paths
	    normalize_printed_paths(pot_path)


def run_msgmerge(po_path: Path, pot_path: Path, *, quiet: bool = False) -> None:
    cmd = [
        "msgmerge",
        "--update",
        "--backup=none",
        str(po_path),
        str(pot_path),
    ]
    run_kwargs = {"check": True}
    if quiet:
        run_kwargs.update({"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True})
    subprocess.run(cmd, **run_kwargs)


def update_translations(locale_dir: str = LOCALE_DIR_DEFAULT, *, skip_po: bool = False, quiet_tools: bool = False) -> None:
    locale_path = Path(locale_dir)
    pot_path = locale_path / "template.pot"

    print("==> Extracting Lua strings (Luanti)")

    lua_files = find_lua_files(".")
    if not lua_files:
        print("No .lua files found")
        return

    locale_path.mkdir(parents=True, exist_ok=True)

    run_xgettext(lua_files, pot_path, quiet=quiet_tools)
    print("==> POT file generated")

    strip_snote_prefix(pot_path)
    print(f"==> S-NOTE prefix stripped in {pot_path}")

    if not skip_po:
        po_files = sorted(locale_path.glob("*.po"))
        if not po_files:
            print(f"No .po files found in {locale_dir}")
        else:
            for po_file in po_files:
                print(f"==> Updating {po_file.name}")
                run_msgmerge(po_file, pot_path, quiet=quiet_tools)

    print("==> Done")


# ====================================================================
# TEST SUITE
# ====================================================================


def _simulate_unescape_c(s: str) -> str:
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nc = s[i + 1]
            if nc == "n":
                result.append("\n")
            elif nc == "t":
                result.append("\t")
            elif nc == "\\":
                result.append("\\")
            elif nc == '"':
                result.append('"')
            elif nc == "r":
                result.append("\r")
            else:
                result.append(nc)
            i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


@contextlib.contextmanager
def _pushd(path: str):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


class FindLuaFilesTests(unittest.TestCase):
    def test_finds_lua_and_excludes_git(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "src"))
            os.makedirs(os.path.join(tmpdir, ".git", "hooks"))
            os.makedirs(os.path.join(tmpdir, "mods", "mymod"))
            Path(tmpdir, "init.lua").touch()
            Path(tmpdir, "src", "util.lua").touch()
            Path(tmpdir, "mods", "mymod", "init.lua").touch()
            Path(tmpdir, ".git", "hooks", "pre-commit.lua").touch()
            Path(tmpdir, "README.md").touch()

            with _pushd(tmpdir):
                files = find_lua_files(".")

            basenames = sorted(os.path.basename(f) for f in files)
            self.assertEqual(basenames, ["init.lua", "init.lua", "util.lua"])
            self.assertNotIn(".git", " ".join(files))
            self.assertFalse(any("README" in f for f in files))

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with _pushd(tmpdir):
                files = find_lua_files(".")
            self.assertEqual(files, [])


class StripSnotePrefixTests(unittest.TestCase):
    def test_strips_only_translator_comment_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pot = Path(tmpdir) / "test.pot"
            pot.write_text(
                '#. S-NOTE: Keep this short\n'
                '#: src/init.lua:10\n'
                'msgid "Hello"\n'
                'msgstr ""\n'
                '\n'
                '# S-NOTE: Another note\n'
                '#: S-NOTE: location note\n'
                '#. Normal comment\n'
                'msgid "World"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            strip_snote_prefix(pot)
            content = pot.read_text(encoding="utf-8")
            self.assertIn("#. Keep this short\n", content)
            self.assertIn("# S-NOTE: Another note\n", content)
            self.assertIn("#: S-NOTE: location note\n", content)
            self.assertIn("#. Normal comment\n", content)
            self.assertIn('msgid "Hello"', content)

    def test_idempotent_when_no_matching_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pot = Path(tmpdir) / "clean.pot"
            original = 'msgid "test"\nmsgstr ""\n'
            pot.write_text(original, encoding="utf-8")
            strip_snote_prefix(pot)
            self.assertEqual(pot.read_text(encoding="utf-8"), original)

    def test_multiline_and_empty_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pot = Path(tmpdir) / "edge.pot"
            pot.write_text(
                '#. S-NOTE: Line one of multi-line comment\n'
                '#. S-NOTE: Line two of multi-line comment\n'
                'msgid "Multi"\n'
                'msgstr ""\n'
                '\n'
                '# Not an S-NOTE comment\n'
                'msgid "Other"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )
            strip_snote_prefix(pot)
            content = pot.read_text(encoding="utf-8")
            self.assertIn("#. Line one of multi-line comment\n", content)
            self.assertIn("#. Line two of multi-line comment\n", content)
            self.assertIn("# Not an S-NOTE comment\n", content)

            empty = Path(tmpdir) / "empty.pot"
            empty.write_text("", encoding="utf-8")
            strip_snote_prefix(empty)
            self.assertEqual(empty.read_text(encoding="utf-8"), "")


class KeywordsTests(unittest.TestCase):
    def test_keyword_set(self):
        expected = {
            "--keyword=S",
            "--keyword=PS:1,2",
            "--keyword=NS",
            "--keyword=FS",
            "--keyword=FPS:1,2",
            "--keyword=NFS",
        }
        self.assertEqual(len(XGETTEXT_KEYWORDS), 6)
        self.assertEqual(set(XGETTEXT_KEYWORDS), expected)

    def test_snote_patterns(self):
        test_lines = [
            ("#. S-NOTE: Keep short", "#. Keep short"),
            ("# S-NOTE: A note", "# S-NOTE: A note"),
            ("#: S-NOTE: loc note", "#: S-NOTE: loc note"),
            ("#. Normal comment", "#. Normal comment"),
            ('#. S-NOTE: has "quotes"', '#. has "quotes"'),
            ("#. S-NOTE: ", "#. "),
        ]
        for input_line, expected_line in test_lines:
            result_line = SNOTE_PATTERN.sub(SNOTE_REPLACEMENT, input_line)
            self.assertEqual(result_line, expected_line)


class PoCompatibilityTests(unittest.TestCase):
    def test_common_c_escapes_roundtrip(self):
        escape_cases = [
            ("Hello", "Hello"),
            ("Line1\\nLine2", "Line1\nLine2"),
            ('say \\"hi\\"', 'say "hi"'),
            ("path\\\\file", "path\\file"),
            ("tab\\there", "tab\there"),
            ("cr\\rline", "cr\rline"),
        ]
        for po_str, expected in escape_cases:
            self.assertEqual(_simulate_unescape_c(po_str), expected)

class UpdateTranslationsTests(unittest.TestCase):
    def test_no_lua_files_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with _pushd(tmpdir):
                captured = io.StringIO()
                with contextlib.redirect_stdout(captured):
                    update_translations("locale")
            self.assertIn("No .lua files found", captured.getvalue())

    @unittest.skipUnless(
        shutil.which("xgettext") is not None and shutil.which("msgmerge") is not None,
        "xgettext/msgmerge not installed",
    )
    def test_full_pipeline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with _pushd(tmpdir):
                locale_dir = Path("locale")
                locale_dir.mkdir()
                Path("init.lua").write_text(
                    'local S = core.get_translator("testmod")\n'
                    'local NS = function(s) return s end\n'
                    '\n'
                    '-- S-NOTE: Keep this greeting short\n'
                    'core.chat_send_all(S("Hello world!"))\n'
                    '\n'
                    '-- S-NOTE: This is a farewell message\n'
                    '-- S-NOTE: used when a player leaves\n'
                    'core.chat_send_all(S("Goodbye!"))\n'
                    '\n'
                    'local untranslated = NS("Not translated here")\n'
                    '\n'
                    'local msg = S("Line 1\\nLine 2")\n',
                    encoding="utf-8",
                )
                (locale_dir / "it.po").write_text(
                    'msgid ""\n'
                    'msgstr ""\n'
                    '"Content-Type: text/plain; charset=UTF-8\\n"\n'
                    '"Content-Transfer-Encoding: 8bit\\n"\n'
                    '\n'
                    'msgid "Hello world!"\n'
                    'msgstr "Ciao mondo!"\n',
                    encoding="utf-8",
                )
                update_translations("locale", quiet_tools=True)

                pot_path = locale_dir / "template.pot"
                self.assertTrue(pot_path.exists())
                pot_content = pot_path.read_text(encoding="utf-8")
                self.assertIn('msgid "Hello world!"', pot_content)
                self.assertIn('msgid "Goodbye!"', pot_content)
                self.assertIn('msgid "Not translated here"', pot_content)
                self.assertNotIn("#. S-NOTE:", pot_content)
                self.assertIn("Keep this greeting short", pot_content)

                po_content = (locale_dir / "it.po").read_text(encoding="utf-8")
                self.assertIn('msgstr "Ciao mondo!"', po_content)
                self.assertIn("Goodbye", po_content)


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


# ====================================================================
# CLI
# ====================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Luanti xgettext helper script. "
            "Extracts translatable strings from .lua files, generates .pot, "
            "strips S-NOTE prefixes, and updates existing .po files."
        ),
    )
    parser.add_argument(
        "locale_dir",
        nargs="?",
        default=LOCALE_DIR_DEFAULT,
        help=f"Path to the locale directory (default: {LOCALE_DIR_DEFAULT})",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run the built-in test suite instead of updating translations.",
    )
    parser.add_argument(
        "-s", "--skip-po",
        action="store_true",
        help="Skip the update of .po files",
    )
    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        update_translations(args.locale_dir, skip_po=args.skip_po)
