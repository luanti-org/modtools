# CC0
# .tr to .po converter for Luanti mods
#
# Escape rules for .tr format (per src/translation.cpp in luanti-org/luanti):
#   @=  -> literal =
#   @n  -> literal newline
#   @   at end of line -> continuation (newline + next line)
#   @X  (any other X) -> preserved as @X literally
#
# Continuation is handled character-by-character inside the entry parser,
# not as a line preprocessor, because it only applies to translation entries
# (not to comments or section markers).

import argparse
import datetime
import pathlib
import sys

BOM_UTF8 = "\ufeff"


def escape_po(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def write_header(f, *, is_pot=False, language=None):
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M+0000"
    )
    f.write('msgid ""\n')
    f.write('msgstr ""\n')
    f.write('"Project-Id-Version: Luanti Mod\\n"\n')
    f.write(f'"POT-Creation-Date: {now}\\n"\n')
    if not is_pot:
        f.write(f'"PO-Revision-Date: {now}\\n"\n')
        if language:
            f.write(f'"Language: {language}\\n"\n')
    f.write('"MIME-Version: 1.0\\n"\n')
    f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
    f.write('"Content-Transfer-Encoding: 8bit\\n"\n\n')


def read_raw_lines(filepath: pathlib.Path):
    with filepath.open(encoding="utf-8-sig") as f:
        for raw_line in f:
            yield raw_line.rstrip("\r\n")


def read_raw_lines_from_string(data: str):
    if data.startswith(BOM_UTF8):
        data = data[1:]
    for raw_line in data.split("\n"):
        yield raw_line.rstrip("\r")


def parse_tr_entry_side(line: str, start: int, lines_iter, stop_at_eq: bool):
    """
    Parse one side of a .tr entry character by character. When stop_at_eq
    is True, stops at the first unescaped '=' (parsing the msgid side).
    When False, reads to end of line/continuation (parsing the msgstr side).

    @ followed by = or n produces the literal character. @ followed by
    anything else preserves both characters. A bare @ at end of line
    consumes the next line from lines_iter as a continuation.

    Returns (parsed_string, current_line, current_position, found_eq).
    """
    result = []
    i = start

    while i < len(line):
        ch = line[i]

        if stop_at_eq and ch == '=':
            return (''.join(result), line, i, True)

        if ch == '@':
            if i + 1 < len(line):
                next_ch = line[i + 1]
                if next_ch == '=':
                    result.append('=')
                elif next_ch == 'n':
                    result.append('\n')
                else:
                    result.append('@')
                    result.append(next_ch)
                i += 2
            else:
                result.append('\n')
                next_line = next(lines_iter, None)
                if next_line is None:
                    break
                line = next_line
                i = 0
        else:
            result.append(ch)
            i += 1

    return (''.join(result), line, i, False)


def parse_tr_file(lines_iter):
    """
    Parse .tr lines, yielding (comments, msgid, msgstr) for each entry.
    Comments, textdomain lines, blank lines, and the NOT USED ANYMORE
    section are handled at the line level before entry parsing begins.
    """
    in_not_used = False
    pending_comments = []

    for line in lines_iter:
        stripped = line.strip()

        if stripped == "##[ NOT USED ANYMORE ]##":
            in_not_used = True
            pending_comments.clear()
            continue
        if stripped == "##[]##" and in_not_used:
            in_not_used = False
            continue
        if in_not_used:
            continue

        if line.startswith("# textdomain:") or line.startswith("##["):
            continue

        if line.startswith("#"):
            comment_text = line[1:]
            if comment_text and comment_text[0] == ' ':
                comment_text = comment_text[1:]
            pending_comments.append(comment_text)
            continue

        if not stripped:
            pending_comments.clear()
            continue

        msgid, line, pos, found_eq = parse_tr_entry_side(
            line, 0, lines_iter, stop_at_eq=True
        )

        if not found_eq:
            pending_comments.clear()
            continue

        msgstr, line, pos, _ = parse_tr_entry_side(
            line, pos + 1, lines_iter, stop_at_eq=False
        )

        comments = pending_comments[:]
        pending_comments.clear()
        yield (comments, msgid, msgstr)


def template_to_pot(template_path: pathlib.Path) -> int:
    pot_path = template_path.with_suffix(".pot")
    count = 0
    with pot_path.open("w", encoding="utf-8") as dst:
        write_header(dst, is_pot=True)
        for comments, msgid, _msgstr in parse_tr_file(
            read_raw_lines(template_path)
        ):
            for c in comments:
                dst.write(f"#. {c}\n")
            dst.write(f'msgid "{escape_po(msgid)}"\n')
            dst.write('msgstr ""\n\n')
            count += 1
    print(f"Created {pot_path.name} ({count} strings)")
    return count


def tr_to_po(tr_path: pathlib.Path) -> int:
    po_path = tr_path.with_suffix(".po")
    language = tr_path.stem
    count = 0
    with po_path.open("w", encoding="utf-8") as dst:
        write_header(dst, is_pot=False, language=language)
        for comments, msgid, msgstr in parse_tr_file(
            read_raw_lines(tr_path)
        ):
            for c in comments:
                dst.write(f"#. {c}\n")
            dst.write(f'msgid "{escape_po(msgid)}"\n')
            dst.write(f'msgstr "{escape_po(msgstr)}"\n\n')
            count += 1
    print(f"Created {po_path.name} ({count} entries, language={language})")
    return count


def convert_locale(locale_dir: str):
    locale_path = pathlib.Path(locale_dir)
    print(f"Locale directory: {locale_path.resolve()}")

    if not locale_path.exists():
        print(f"Error: locale directory '{locale_path}' not found.", file=sys.stderr)
        sys.exit(1)

    if not locale_path.is_dir():
        print(f"Error: '{locale_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    errors = []

    template = locale_path / "template.txt"
    if template.exists():
        try:
            template_to_pot(template)
            template.unlink()
            print("Removed template.txt")
        except Exception as e:
            errors.append(f"Failed to convert template.txt: {e}")
            print(f"Error: {errors[-1]}", file=sys.stderr)
    else:
        print("No template.txt found")

    tr_files = sorted(locale_path.glob("*.tr"))
    if not tr_files:
        print("No .tr files found")

    for tr_file in tr_files:
        try:
            tr_to_po(tr_file)
            tr_file.unlink()
            print(f"Removed {tr_file.name}")
        except Exception as e:
            errors.append(f"Failed to convert {tr_file.name}: {e}")
            print(f"Error: {errors[-1]}", file=sys.stderr)

    if errors:
        print(f"\nMigration completed with {len(errors)} error(s).", file=sys.stderr)
    else:
        print("Migration completed successfully.")


# ====================================================================
# TEST SUITE
# ====================================================================

def count_po_entries(po_text: str) -> int:
    return po_text.count('msgid "') - 1


def run_tests():
    import tempfile
    import os

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

    def parse_string(data):
        return list(parse_tr_file(read_raw_lines_from_string(data)))

    # =================================================================
    section("escape_po")
    # =================================================================

    check("1.1 plain text",
          escape_po("Hello"), "Hello")
    check("1.2 newline",
          escape_po("Line1\nLine2"), "Line1\\nLine2")
    check("1.3 backslash",
          escape_po("path\\file"), "path\\\\file")
    check("1.4 quote",
          escape_po('say "hi"'), 'say \\"hi\\"')
    check("1.5 all three",
          escape_po('a\\b\n"c"'), 'a\\\\b\\n\\"c\\"')
    check("1.6 @ passthrough",
          escape_po("user@@domain"), "user@@domain")

    # =================================================================
    section("parse_tr_entry_side")
    # =================================================================

    result, _, pos, found = parse_tr_entry_side("Hello=World", 0, iter([]), True)
    check("2.1 simple msgid", (result, found), ("Hello", True))

    result, _, pos, found = parse_tr_entry_side("a@=b=c", 0, iter([]), True)
    check("2.2 @= in msgid", (result, found), ("a=b", True))

    result, _, pos, found = parse_tr_entry_side("x@ny=z", 0, iter([]), True)
    check("2.3 @n in msgid", (result, found), ("x\ny", True))

    result, _, pos, found = parse_tr_entry_side("a@@b=c", 0, iter([]), True)
    check("2.4 @@ preserved", (result, found), ("a@@b", True))

    result, _, pos, found = parse_tr_entry_side("a@Zb=c", 0, iter([]), True)
    check("2.5 @Z preserved", (result, found), ("a@Zb", True))

    result, _, _, found = parse_tr_entry_side("val=ue", 0, iter([]), False)
    check("2.6 msgstr side no split", (result, found), ("val=ue", False))

    lines = iter(["continuation"])
    result, _, _, found = parse_tr_entry_side("start@", 0, lines, False)
    check("2.7 continuation", result, "start\ncontinuation")

    # @= produces '=', then the next char is a bare '=' which is the separator
    result, _, pos, found = parse_tr_entry_side("x@==v", 0, iter([]), True)
    check("2.8 @== splits correctly", (result, found), ("x=", True))

    result, _, _, found = parse_tr_entry_side("no equals", 0, iter([]), True)
    check("2.9 no = found", found, False)

    result, _, _, found = parse_tr_entry_side("", 0, iter([]), True)
    check("2.10 empty input", (result, found), ("", False))

    # =================================================================
    section("parse_tr_file")
    # =================================================================

    entries = parse_string("Hello=World")
    check("3.1 basic entry",
          entries, [([], "Hello", "World")])

    entries = parse_string("# textdomain: test\n# my comment\nHello=World")
    check("3.2 textdomain + comment",
          entries, [(["my comment"], "Hello", "World")])

    entries = parse_string("a @= b@nc=x @= y@nz")
    check("3.3 @= and @n",
          entries, [([], "a = b\nc", "x = y\nz")])

    entries = parse_string(
        "k1=v1\n##[ NOT USED ANYMORE ]##\nold=x\n##[]##\nk2=v2"
    )
    check("3.4 NOT USED filtered",
          entries, [([], "k1", "v1"), ([], "k2", "v2")])

    entries = parse_string("# orphan\n\nkey=val")
    check("3.5 blank resets comments",
          entries, [([], "key", "val")])

    entries = parse_string("k=a=b=c")
    check("3.6 multiple = in value",
          entries, [([], "k", "a=b=c")])

    entries = parse_string("key=")
    check("3.7 empty value",
          entries, [([], "key", "")])

    entries = parse_string("  k  =  v  ")
    check("3.8 spaces preserved",
          entries, [([], "  k  ", "  v  ")])

    entries = parse_string("a@@b=c@@d")
    check("3.9 @@ preserved",
          entries, [([], "a@@b", "c@@d")])

    entries = parse_string('say "hi"\\n=dire "ciao"\\n')
    check("3.10 backslash and quotes passthrough",
          entries, [([], 'say "hi"\\n', 'dire "ciao"\\n')])

    # =================================================================
    section("Comment with @ at end of line")
    # =================================================================

    # A comment line ending with @ is still just a comment. The next
    # line is parsed independently, and the comment is attached to the
    # next entry (unless a blank line resets pending comments).
    entries = parse_string("# textdomain: t\n# c@\nk=v")
    check("4.1 comment@ does not consume next line",
          entries, [(["c@"], "k", "v")])

    entries = parse_string("# first@\n# second\nk=v")
    check("4.2 comment@ then comment then entry",
          entries, [(["first@", "second"], "k", "v")])

    entries = parse_string("# note@n\nk=v")
    check("4.3 comment with @n is just a comment",
          entries, [(["note@n"], "k", "v")])

    # =================================================================
    section("@@ at end of line")
    # =================================================================

    # key@@ has no unescaped '=', so it is malformed and skipped.
    # =v is a separate line with empty msgid.
    entries = parse_string("# textdomain: t\nkey@@\n=v")
    check("5.1 key@@ is malformed",
          len(entries), 1)
    if entries:
        check("5.1b =v parsed as empty key",
              entries[0], ([], "", "v"))

    entries = parse_string("k=val@@")
    check("5.2 @@ at end of value",
          entries, [([], "k", "val@@")])

    # @@@ at end: @@ is preserved (2 chars consumed), then bare @ at EOL
    # triggers continuation with the next line.
    entries = parse_string("k=val@@@\nnext")
    check("5.3 @@@ at end triggers continuation",
          entries, [([], "k", "val@@\nnext")])

    entries = parse_string("k@@=v")
    check("5.4 @@ then bare = in msgid",
          entries, [([], "k@@", "v")])

    # =================================================================
    section("Continuation in entries")
    # =================================================================

    entries = parse_string("first@\nsecond=value")
    check("6.1 continuation in msgid",
          entries, [([], "first\nsecond", "value")])

    entries = parse_string("key=first@\nsecond")
    check("6.2 continuation in msgstr",
          entries, [([], "key", "first\nsecond")])

    entries = parse_string("a@\nb@\nc=x")
    check("6.3 double continuation",
          entries, [([], "a\nb\nc", "x")])

    entries = parse_string("key=val@")
    check("6.4 continuation at EOF",
          entries, [([], "key", "val\n")])

    entries = parse_string("k1@\nk2=v1@\nv2")
    check("6.5 continuation both sides",
          entries, [([], "k1\nk2", "v1\nv2")])

    # =================================================================
    section("File-level integration")
    # =================================================================

    with tempfile.TemporaryDirectory() as tmpdir:
        locale_dir = pathlib.Path(tmpdir) / "locale"
        locale_dir.mkdir()

        (locale_dir / "template.txt").write_text(
            "# textdomain: testmod\n"
            "# Comment for greeting\n"
            "Hello=\n"
            "# Comment for price\n"
            "Price @= 10=\n"
            "Line 1@nLine 2=\n"
            "Simple=\n"
            "##[ NOT USED ANYMORE ]##\n"
            "Old deprecated=\n"
            "##[]##\n"
            "After not used=\n",
            encoding="utf-8",
        )

        (locale_dir / "it.tr").write_text(
            "# textdomain: testmod\n"
            "# Commento per saluto\n"
            "Hello=Ciao\n"
            "# Commento per prezzo\n"
            "Price @= 10=Prezzo @= 10\n"
            "Line 1@nLine 2=Riga 1@nRiga 2\n"
            "Simple=Semplice\n"
            "##[ NOT USED ANYMORE ]##\n"
            "Old deprecated=Vecchio\n"
            "##[]##\n"
            "After not used=Dopo sezione obsoleta\n",
            encoding="utf-8",
        )

        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            convert_locale(str(locale_dir))
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout

        check("7.1 template.txt removed",
              (locale_dir / "template.txt").exists(), False)
        check("7.2 template.pot created",
              (locale_dir / "template.pot").exists(), True)
        check("7.3 it.tr removed",
              (locale_dir / "it.tr").exists(), False)
        check("7.4 it.po created",
              (locale_dir / "it.po").exists(), True)

        pot = (locale_dir / "template.pot").read_text(encoding="utf-8")
        po = (locale_dir / "it.po").read_text(encoding="utf-8")

        check("7.5 POT header",
              'msgid ""\nmsgstr ""' in pot, True)
        check("7.6 POT no PO-Revision-Date",
              "PO-Revision-Date:" not in pot, True)
        check("7.7 POT Hello",
              'msgid "Hello"' in pot, True)
        check("7.8 POT Price = 10",
              'msgid "Price = 10"' in pot, True)
        check("7.9 POT Line 1\\nLine 2",
              'msgid "Line 1\\nLine 2"' in pot, True)
        check("7.10 POT no deprecated",
              "Old deprecated" not in pot, True)
        check("7.11 POT post-deprecated",
              'msgid "After not used"' in pot, True)
        check("7.12 POT comment",
              "#. Comment for greeting" in pot, True)
        check("7.13 POT entry count",
              count_po_entries(pot), 5)

        check("7.14 PO Language: it",
              '"Language: it\\n"' in po, True)
        check("7.15 PO Hello=Ciao",
              'msgid "Hello"\nmsgstr "Ciao"' in po, True)
        check("7.16 PO Price = 10",
              'msgid "Price = 10"\nmsgstr "Prezzo = 10"' in po, True)
        check("7.17 PO multiline",
              'msgid "Line 1\\nLine 2"\nmsgstr "Riga 1\\nRiga 2"' in po, True)
        check("7.18 PO no deprecated",
              "Vecchio" not in po, True)
        check("7.19 PO post-deprecated",
              'msgid "After not used"\nmsgstr "Dopo sezione obsoleta"' in po,
              True)
        check("7.20 PO comment",
              "#. Commento per saluto" in po, True)
        check("7.21 PO entry count",
              count_po_entries(po), 5)

    # =================================================================
    section("File-level edge cases")
    # =================================================================

    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        (d / "empty.tr").write_text(
            "# textdomain: test\n", encoding="utf-8"
        )
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            tr_to_po(d / "empty.tr")
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
        po = (d / "empty.po").read_text(encoding="utf-8")
        check("8.1 empty .tr valid PO",
              'msgid ""' in po and 'msgstr ""' in po, True)
        check("8.1b empty .tr 0 entries",
              count_po_entries(po), 0)

    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        (d / "xx.tr").write_text(
            "# textdomain: t\n##[ NOT USED ANYMORE ]##\nold=x\n",
            encoding="utf-8",
        )
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            tr_to_po(d / "xx.tr")
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
        po = (d / "xx.po").read_text(encoding="utf-8")
        check("8.2 only deprecated 0 entries",
              count_po_entries(po), 0)

    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        (d / "sp.tr").write_text(
            "# textdomain: t\n  k  =  v  \n", encoding="utf-8"
        )
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            tr_to_po(d / "sp.tr")
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
        po = (d / "sp.po").read_text(encoding="utf-8")
        check("8.3 spaces in msgid",
              'msgid "  k  "' in po, True)
        check("8.3b spaces in msgstr",
              'msgstr "  v  "' in po, True)

    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        (d / "bom.tr").write_text(
            BOM_UTF8 + "# textdomain: t\nk=v\n", encoding="utf-8"
        )
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            tr_to_po(d / "bom.tr")
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
        po = (d / "bom.po").read_text(encoding="utf-8")
        check("8.4 UTF-8 BOM handled",
              'msgid "k"' in po, True)

    # =================================================================
    section("Round-trip verification")
    # =================================================================

    def simulate_luanti_po_unescape(po_str: str) -> str:
        result = []
        i = 0
        while i < len(po_str):
            if po_str[i] == '\\' and i + 1 < len(po_str):
                nc = po_str[i + 1]
                if nc == 'n':
                    result.append('\n')
                elif nc == '\\':
                    result.append('\\')
                elif nc == '"':
                    result.append('"')
                else:
                    result.append(nc)
                i += 2
            else:
                result.append(po_str[i])
                i += 1
        return ''.join(result)

    roundtrip_cases = [
        ("Hello=Ciao", "Hello", "Ciao"),
        ("a @= b=x @= y", "a = b", "x = y"),
        ("l1@nl2=r1@nr2", "l1\nl2", "r1\nr2"),
        ("a@@b=c@@d", "a@@b", "c@@d"),
        ('say "hi"=dire "ciao"', 'say "hi"', 'dire "ciao"'),
        ("p\\a\\th=p\\e\\rc", "p\\a\\th", "p\\e\\rc"),
    ]

    for i, (tr_line, exp_id, exp_str) in enumerate(roundtrip_cases):
        entries = parse_string(tr_line)
        if not entries:
            check(f"9.{i+1} parse failed", None, "entry expected")
            continue

        _, msgid, msgstr = entries[0]

        check(f"9.{i+1}a parse msgid",
              msgid, exp_id, f"input: {tr_line!r}")
        check(f"9.{i+1}b parse msgstr",
              msgstr, exp_str, f"input: {tr_line!r}")

        po_id = escape_po(msgid)
        po_str = escape_po(msgstr)
        rt_id = simulate_luanti_po_unescape(po_id)
        rt_str = simulate_luanti_po_unescape(po_str)

        check(f"9.{i+1}c roundtrip msgid",
              rt_id, msgid, f"PO: '{po_id}'")
        check(f"9.{i+1}d roundtrip msgstr",
              rt_str, msgstr, f"PO: '{po_str}'")

    # =================================================================
    # RESULTS
    # =================================================================

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Luanti .tr translation files to gettext .po/.pot format."
    )
    parser.add_argument(
        "locale_dir",
        nargs="?",
        default="locale",
        help="Path to the locale directory (default: locale)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run the built-in test suite instead of converting files.",
    )
    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        convert_locale(args.locale_dir)
