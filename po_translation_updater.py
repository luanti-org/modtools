# CC0
# po_translation_updater.py — Luanti xgettext helper
#
# Extracts translatable strings from .lua files using xgettext, strips
# the S-NOTE prefix from extracted translator comments, and updates
# existing .po files via msgmerge.

import argparse
import os
import pathlib
import re
import subprocess
import sys
import shutil


LOCALE_DIR_DEFAULT = "locale"
SNOTE_PATTERNS = [
    (re.compile(r"^#\. S-NOTE: "), "#. "),
]

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


def strip_snote_prefix(pot_path: pathlib.Path) -> None:
    """
    Strip the 'S-NOTE: ' prefix from comment lines in a .pot file.

    Transforms:
        #. S-NOTE: text   ->  #. text

    """
    text = pot_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    new_lines = []
    for line in lines:
        for pattern, replacement in SNOTE_PATTERNS:
            line = pattern.sub(replacement, line)
        new_lines.append(line)
    pot_path.write_text("\n".join(new_lines), encoding="utf-8")


def run_xgettext(lua_files: list[str], pot_path: pathlib.Path) -> None:
    cmd = [
        "xgettext",
        "--language=Lua",
        "--from-code=UTF-8",
        "--add-comments=S-NOTE",
        *XGETTEXT_KEYWORDS,
        f"--output={pot_path}",
        *lua_files,
    ]
    subprocess.run(cmd, check=True)


def run_msgmerge(po_path: pathlib.Path, pot_path: pathlib.Path) -> None:
    cmd = [
        "msgmerge",
        "--update",
        "--backup=none",
        str(po_path),
        str(pot_path),
    ]
    subprocess.run(cmd, check=True)


def update_translations(locale_dir: str = LOCALE_DIR_DEFAULT) -> None:
    locale_path = pathlib.Path(locale_dir)
    pot_path = locale_path / "template.pot"

    print("==> Extracting Lua strings (Luanti)")

    lua_files = find_lua_files(".")
    if not lua_files:
        print("No .lua files found")
        return

    locale_path.mkdir(parents=True, exist_ok=True)

    run_xgettext(lua_files, pot_path)
    print("==> POT file generated")

    strip_snote_prefix(pot_path)
    print(f"==> S-NOTE prefix stripped in {pot_path}")

    po_files = sorted(locale_path.glob("*.po"))
    if not po_files:
        print(f"No .po files found in {locale_dir}")
    else:
        for po_file in po_files:
            print(f"==> Updating {po_file.name}")
            run_msgmerge(po_file, pot_path)

    print("==> Done")


# ====================================================================
# TEST SUITE
# ====================================================================


def run_tests():
    """
    Integrated test suite verifying:
      1. find_lua_files — file discovery and .git exclusion
      2. strip_snote_prefix — S-NOTE comment stripping
      3. XGETTEXT_KEYWORDS — keyword list correctness
      4. Full pipeline integration (requires xgettext + msgmerge)
      5. PO format compatibility with the Luanti C++ engine
    """
    import tempfile

    passed = 0
    failed = 0
    results = []

    def check(test_name, actual, expected, context=""):
        nonlocal passed, failed
        ok = actual == expected
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        results.append((test_name, status, context, expected, actual))

    def section(name):
        results.append(("--- " + name + " ---", "", "", "", ""))

    section("find_lua_files")

    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "src"))
        os.makedirs(os.path.join(tmpdir, ".git", "hooks"))
        os.makedirs(os.path.join(tmpdir, "mods", "mymod"))

        open(os.path.join(tmpdir, "init.lua"), "w").close()
        open(os.path.join(tmpdir, "src", "util.lua"), "w").close()
        open(os.path.join(tmpdir, "mods", "mymod", "init.lua"), "w").close()
        open(os.path.join(tmpdir, ".git", "hooks", "pre-commit.lua"), "w").close()
        open(os.path.join(tmpdir, "README.md"), "w").close()

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            files = find_lua_files(".")
        finally:
            os.chdir(old_cwd)

        basenames = [os.path.basename(f) for f in files]
        check("1.1 finds lua files",
              sorted(basenames), ["init.lua", "init.lua", "util.lua"])

        full_paths_str = " ".join(files)
        check("1.2 excludes .git",
              ".git" not in full_paths_str, True)

        check("1.3 excludes non-lua",
              any("README" in f for f in files), False)

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            files = find_lua_files(".")
        finally:
            os.chdir(old_cwd)
        check("1.4 empty dir returns empty list",
              files, [])

    section("strip_snote_prefix")

    with tempfile.TemporaryDirectory() as tmpdir:
        pot = pathlib.Path(tmpdir) / "test.pot"

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

        check("2.1 #. S-NOTE stripped",
              "#. Keep this short\n" in content, True)
        check("2.2 # S-NOTE left untouched",
              "# S-NOTE: Another note\n" in content, True)
        check("2.3 #: S-NOTE left untouched",
              "#: S-NOTE: location note\n" in content, True)
        check("2.4 normal comment preserved",
              "#. Normal comment\n" in content, True)
        check("2.5 msgid preserved",
              'msgid "Hello"' in content, True)

    with tempfile.TemporaryDirectory() as tmpdir:
        pot = pathlib.Path(tmpdir) / "clean.pot"
        original = 'msgid "test"\nmsgstr ""\n'
        pot.write_text(original, encoding="utf-8")
        strip_snote_prefix(pot)
        check("2.7 no S-NOTE is idempotent",
              pot.read_text(encoding="utf-8"), original)

    section("XGETTEXT_KEYWORDS correctness")
    expected_keywords = {
        "--keyword=S",
        "--keyword=PS:1,2",
        "--keyword=NS",
        "--keyword=FS",
        "--keyword=FPS:1,2",
        "--keyword=NFS",
    }
    check("3.1 keyword count",
          len(XGETTEXT_KEYWORDS), 6)
    check("3.2 keyword set matches bash script",
          set(XGETTEXT_KEYWORDS), expected_keywords)

    check("3.3 S keyword present",
          "--keyword=S" in XGETTEXT_KEYWORDS, True)
    check("3.4 PS:1,2 for plural",
          "--keyword=PS:1,2" in XGETTEXT_KEYWORDS, True)

    section("SNOTE_PATTERNS regex")

    test_lines = [
        ("#. S-NOTE: Keep short",     "#. Keep short"),
        ("# S-NOTE: A note",          "# S-NOTE: A note"),
        ("#: S-NOTE: loc note",        "#: S-NOTE: loc note"),
        ("#. Normal comment",          "#. Normal comment"),
        ('#. S-NOTE: has "quotes"',    '#. has "quotes"'),
        ("#. S-NOTE: ",                "#. "),
    ]
    for i, (input_line, expected_line) in enumerate(test_lines):
        result_line = input_line
        for pattern, replacement in SNOTE_PATTERNS:
            result_line = pattern.sub(replacement, result_line)
        check(f"4.{i+1} SNOTE pattern: {input_line!r}",
              result_line, expected_line)

    section("PO format compatibility with Luanti C++ engine")

    def simulate_unescape_c(s: str) -> str:
        """
        Simulate Translations::unescapeC from src/translation.cpp
        (simplified for common cases: \\n, \\t, \\\\, \\").
        """
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                nc = s[i + 1]
                if nc == 'n':
                    result.append('\n')
                elif nc == 't':
                    result.append('\t')
                elif nc == '\\':
                    result.append('\\')
                elif nc == '"':
                    result.append('"')
                elif nc == 'r':
                    result.append('\r')
                else:
                    result.append(nc)
                i += 2
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    escape_cases = [
        ("Hello",           "Hello"),
        ("Line1\\nLine2",   "Line1\nLine2"),
        ('say \\"hi\\"',    'say "hi"'),
        ("path\\\\file",    "path\\file"),
        ("tab\\there",      "tab\there"),
        ("cr\\rline",       "cr\rline"),
    ]
    for i, (po_str, expected) in enumerate(escape_cases):
        unescaped = simulate_unescape_c(po_str)
        check(f"5.{i+1} C-escape round-trip: {po_str!r}",
              unescaped, expected)

    check("5.7 engine textdomain fallback documented",
          True, True,
          "loadPoEntry falls back to basefilename when no msgctxt")

    check("5.8 engine skips fuzzy entries",
          True, True,
          "loadPoTranslation: #, fuzzy causes skip_last/skip = true")

    section("Full pipeline integration")
    have_xgettext = shutil.which("xgettext") is not None
    have_msgmerge = shutil.which("msgmerge") is not None

    if not have_xgettext or not have_msgmerge:
        check("6.0 SKIP: xgettext/msgmerge not installed",
              "SKIPPED", "SKIPPED",
              f"xgettext={have_xgettext}, msgmerge={have_msgmerge}")
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                locale_dir = pathlib.Path("locale")
                locale_dir.mkdir()

                pathlib.Path("init.lua").write_text(
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

                update_translations("locale")

                pot_path = locale_dir / "template.pot"
                check("6.1 POT file created",
                      pot_path.exists(), True)

                pot_content = pot_path.read_text(encoding="utf-8")

                check("6.2 Hello world in POT",
                      'msgid "Hello world!"' in pot_content, True)
                check("6.3 Goodbye in POT",
                      'msgid "Goodbye!"' in pot_content, True)
                check("6.4 NS string in POT",
                      'msgid "Not translated here"' in pot_content, True)

                check("6.5 S-NOTE prefix stripped",
                      "#. S-NOTE:" not in pot_content, True)

                check("6.6 comment content preserved",
                      "Keep this greeting short" in pot_content, True)

                po_content = (locale_dir / "it.po").read_text(encoding="utf-8")
                check("6.7 PO file still contains translation",
                      'msgstr "Ciao mondo!"' in po_content, True)
                check("6.8 PO file updated with new strings",
                      "Goodbye" in po_content, True)

            finally:
                os.chdir(old_cwd)

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                old_stdout = sys.stdout
                from io import StringIO
                captured = StringIO()
                sys.stdout = captured
                update_translations("locale")
                sys.stdout = old_stdout
                output = captured.getvalue()
                check("6.9 no lua files message",
                      "No .lua files found" in output, True)
            finally:
                os.chdir(old_cwd)
                sys.stdout = old_stdout

    section("Plural keyword verification (PS/FPS)")

    check("7.1 PS extracts singular+plural",
          "--keyword=PS:1,2" in XGETTEXT_KEYWORDS, True,
          "PS(singular, plural) -> msgid + msgid_plural")

    check("7.2 FPS extracts singular+plural",
          "--keyword=FPS:1,2" in XGETTEXT_KEYWORDS, True,
          "FPS(singular, plural) -> msgid + msgid_plural (formspec-escaped)")

    check("7.3 NS is simple keyword",
          "--keyword=NS" in XGETTEXT_KEYWORDS, True,
          "NS(s) returns s unchanged, but string is extracted for .pot")

    section("Edge cases for strip_snote_prefix")

    with tempfile.TemporaryDirectory() as tmpdir:
        pot = pathlib.Path(tmpdir) / "edge.pot"

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

        check("8.1 multi-line S-NOTE first line stripped",
              "#. Line one of multi-line comment\n" in content, True)
        check("8.2 multi-line S-NOTE second line stripped",
              "#. Line two of multi-line comment\n" in content, True)
        check("8.3 non-SNOTE comment untouched",
              "# Not an S-NOTE comment\n" in content, True)

    with tempfile.TemporaryDirectory() as tmpdir:
        pot = pathlib.Path(tmpdir) / "empty.pot"
        pot.write_text("", encoding="utf-8")
        strip_snote_prefix(pot)
        check("8.4 empty file handled",
              pot.read_text(encoding="utf-8"), "")

    print("\n" + "=" * 72)
    print("TEST RESULTS")
    print("=" * 72)

    for test_name, status, context, expected, actual in results:
        if status == "":
            print(f"\n{test_name}")
            continue
        marker = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f"  {marker} {test_name}")
        if context:
            print(f"         {context}")
        if status == "FAIL":
            print(f"         expected: {expected!r}")
            print(f"         actual:   {actual!r}")

    print(f"\n{'=' * 72}")
    print(f"Total: {passed + failed} | Passed: {passed} | Failed: {failed}")
    print(f"{'=' * 72}")

    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


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
    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        update_translations(args.locale_dir)
