# CC0
# .tr to .po converter for Luanti mods
#
# Reference: src/translation.cpp from luanti-org/luanti
# Escape rules for .tr format:
#   @=  -> literal =
#   @n  -> literal newline
#   @\n (@ at end of line) -> continuation (newline + next line)
#   @X  (any other X) -> preserved as @X literally

import argparse
import datetime
import pathlib
import sys


def parse_tr_escapes(raw: str) -> str:
    """
    Process .tr escape sequences faithfully to the Luanti C++ parser:
      @=  -> =
      @n  -> newline character
      @X  (anything else) -> @X  (both characters preserved)

    Note: @@ is NOT a special case in Luanti. @@ stays as @@.
    The "@ at end of line" (continuation) case is handled at the
    line-reading level, not here.
    """
    result = []
    i = 0
    while i < len(raw):
        if raw[i] == '@' and i + 1 < len(raw):
            next_ch = raw[i + 1]
            if next_ch == '=':
                result.append('=')
                i += 2
            elif next_ch == 'n':
                result.append('\n')
                i += 2
            else:
                # All other escapes are preserved as-is
                result.append('@')
                result.append(next_ch)
                i += 2
        else:
            result.append(raw[i])
            i += 1
    return ''.join(result)


def split_tr_line(line: str):
    """
    Split a .tr line on the first unescaped '='.
    In .tr format, @= is an escaped literal '=', not a separator.
    Mirrors the C++ parser: scan left-to-right, skip @= and @n,
    split on the first bare '='.

    Returns (raw_left, raw_right) or None if no unescaped '=' found.
    The raw parts still contain .tr escape sequences.
    """
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '@':
            # Skip the escape sequence (two characters)
            i += 2
            continue
        if ch == '=':
            return (line[:i], line[i + 1:])
        i += 1
    return None


def escape_po(s: str) -> str:
    """
    Escape a string for use inside PO double-quoted strings.
    """
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def write_header(f, *, is_pot=False, language=None):
    """
    Write a standard PO/POT header.
    """
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M+0000")

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


def read_tr_lines(filepath: pathlib.Path):
    """
    Read a .tr file and yield logical lines, handling the @ continuation
    (bare @ at end of line means the entry continues on the next line,
    with a newline inserted).
    Also strips \\r for Windows line endings.
    """
    with filepath.open(encoding="utf-8") as f:
        continuation = None
        for raw_line in f:
            raw_line = raw_line.rstrip("\r\n")

            if continuation is not None:
                raw_line = continuation + raw_line
                continuation = None

            # Check if line ends with a bare @ (continuation marker).
            # A bare @ at end of line is one that is not part of an @@ or
            # other escape sequence. The C++ parser just checks if @ is
            # the very last character.
            if raw_line.endswith("@"):
                # Replace trailing @ with @n (which will become \n after
                # unescape) and continue reading.
                continuation = raw_line[:-1] + "@n"
                continue

            yield raw_line

        # If file ended mid-continuation, yield what we have
        if continuation is not None:
            yield continuation


# ------------------ POT generation ------------------

def template_to_pot(template_path: pathlib.Path) -> int:
    """
    Convert template.txt to template.pot, preserving translator comments (#.).
    Skips the "NOT USED ANYMORE" section.
    """
    pot_path = template_path.with_suffix(".pot")
    count = 0
    in_not_used = False

    with pot_path.open("w", encoding="utf-8") as dst:
        write_header(dst, is_pot=True)
        pending_comments = []

        for line in read_tr_lines(template_path):
            # Handle NOT USED ANYMORE section
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

            # Skip textdomain and internal section markers
            if line.startswith("# textdomain:") or line.startswith("##["):
                continue

            # Translator comments
            if line.startswith("#"):
                comment_text = line[1:]
                if comment_text and comment_text[0] == ' ':
                    comment_text = comment_text[1:]
                pending_comments.append(comment_text)
                continue

            # Empty or whitespace-only lines reset pending comments
            if not stripped:
                pending_comments.clear()
                continue

            # Template lines: "msgid=" (value side is empty)
            split = split_tr_line(line)
            if split is None:
                # No unescaped '=' found, skip
                pending_comments.clear()
                continue

            raw_msgid = split[0]
            msgid = parse_tr_escapes(raw_msgid)

            for c in pending_comments:
                dst.write(f"#. {c}\n")
            pending_comments.clear()

            dst.write(f'msgid "{escape_po(msgid)}"\n')
            dst.write('msgstr ""\n\n')
            count += 1

    print(f"Created {pot_path.name} ({count} strings)")
    return count


# ------------------ TR to PO conversion ------------------

def tr_to_po(tr_path: pathlib.Path) -> int:
    """
    Convert a .tr file to a .po file, preserving translator comments (#.).
    Skips the "NOT USED ANYMORE" section.
    """
    po_path = tr_path.with_suffix(".po")
    language = tr_path.stem
    count = 0
    in_not_used = False

    with po_path.open("w", encoding="utf-8") as dst:
        write_header(dst, is_pot=False, language=language)
        pending_comments = []

        for line in read_tr_lines(tr_path):
            # Handle NOT USED ANYMORE section
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

            # Skip textdomain and internal section markers
            if line.startswith("# textdomain:") or line.startswith("##["):
                continue

            # Translator comments
            if line.startswith("#"):
                comment_text = line[1:]
                if comment_text and comment_text[0] == ' ':
                    comment_text = comment_text[1:]
                pending_comments.append(comment_text)
                continue

            # Empty or whitespace-only lines reset pending comments
            if not stripped:
                pending_comments.clear()
                continue

            split = split_tr_line(line)
            if split is None:
                pending_comments.clear()
                continue

            raw_msgid, raw_msgstr = split
            msgid = parse_tr_escapes(raw_msgid)
            msgstr = parse_tr_escapes(raw_msgstr)

            for c in pending_comments:
                dst.write(f"#. {c}\n")
            pending_comments.clear()

            dst.write(f'msgid "{escape_po(msgid)}"\n')
            dst.write(f'msgstr "{escape_po(msgstr)}"\n\n')
            count += 1

    print(f"Created {po_path.name} ({count} entries, language={language})")
    return count


# ------------------ Locale conversion ------------------

def convert_locale(locale_dir: str):
    """
    Main entry point: convert template.txt and all .tr files in the given
    locale directory to .pot/.po, then remove the originals.
    """
    locale_path = pathlib.Path(locale_dir)
    print(f"Locale directory: {locale_path.resolve()}")

    if not locale_path.exists():
        print(f"Error: locale directory '{locale_path}' not found.", file=sys.stderr)
        sys.exit(1)

    if not locale_path.is_dir():
        print(f"Error: '{locale_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    errors = []

    # template.txt -> template.pot
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

    # Convert all .tr -> .po
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
    args = parser.parse_args()
    convert_locale(args.locale_dir)