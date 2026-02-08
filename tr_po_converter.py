# CC0, completely vibecoded

import datetime
import pathlib


def escape_po(s: str) -> str:
    """
    Escape backslashes, quotes, and newlines for PO format.
    """
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def write_header(f, *, is_pot=False, language=None):
    """
    Write standard PO/POT header.
    """
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M+0000")

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


# ------------------ POT generation ------------------

def template_to_pot(template_path: pathlib.Path) -> int:
    """
    Convert template.txt to template.pot, preserving translator comments (#.).
    """
    pot_path = template_path.with_suffix(".pot")
    count = 0

    with template_path.open(encoding="utf-8") as src, \
         pot_path.open("w", encoding="utf-8") as dst:

        write_header(dst, is_pot=True)
        pending_comments = []

        for line in src:
            line = line.rstrip("\n")

            # Skip internal comments and textdomain
            if line.startswith("##[") or line.startswith("# textdomain"):
                continue

            if line.startswith("#"):
                pending_comments.append(line[1:].strip())
                continue

            if not line:
                pending_comments.clear()
                continue

            if line.endswith("="):
                line = line[:-1]

            for c in pending_comments:
                dst.write(f"#. {c}\n")
            pending_comments.clear()

            dst.write(f'msgid "{escape_po(line)}"\n')
            dst.write('msgstr ""\n\n')
            count += 1

    print(f"Created {pot_path.name} ({count} strings)")
    return count


# ------------------ TR to PO conversion ------------------

def tr_to_po(tr_path: pathlib.Path) -> int:
    """
    Convert a .tr file to a .po file, preserving translator comments (#.).
    """
    po_path = tr_path.with_suffix(".po")
    language = tr_path.stem
    count = 0

    with tr_path.open(encoding="utf-8") as src, \
         po_path.open("w", encoding="utf-8") as dst:

        write_header(dst, is_pot=False, language=language)
        pending_comments = []

        for line in src:
            line = line.rstrip("\n")

            # Skip internal comments and textdomain
            if line.startswith("##[") or line.startswith("# textdomain"):
                continue

            if line.startswith("#"):
                pending_comments.append(line[1:].strip())
                continue

            if "=" not in line:
                continue

            msgid, msgstr = line.split("=", 1)
            msgid, msgstr = msgid.strip(), msgstr.strip()

            for c in pending_comments:
                dst.write(f"#. {c}\n")
            pending_comments.clear()

            dst.write(f'msgid "{escape_po(msgid)}"\n')
            dst.write(f'msgstr "{escape_po(msgstr)}"\n\n')
            count += 1

    print(f"Created {po_path.name} ({count} entries, language={language})")
    return count


# ------------------ Locale conversion ------------------

def convert_locale(locale_dir="locale"):
    """
    Main function to convert template.txt and .tr files to POT and PO files.
    """
    locale_dir = pathlib.Path(locale_dir)
    print(f"📁 Locale directory: {locale_dir.resolve()}")

    if not locale_dir.exists():
        print("❌ Locale directory not found")
        return

    # template.txt → template.pot
    template = locale_dir / "template.txt"
    if template.exists():
        template_to_pot(template)
        template.unlink()
        print("Removed template.txt")
    else:
        print("No template.txt found")

    # Convert all .tr → .po
    tr_files = list(locale_dir.glob("*.tr"))
    if not tr_files:
        print("No .tr files found")

    for tr_file in tr_files:
        tr_to_po(tr_file)
        tr_file.unlink()
        print(f"Removed {tr_file.name}")

    print("✅ Migration completed successfully")


if __name__ == "__main__":
    convert_locale("locale")

