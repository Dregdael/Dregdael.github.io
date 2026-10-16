#!/usr/bin/env python3
"""Generate AcademicPages publication Markdown files from one or more BibTeX files."""

import argparse
import html
import json
import os
import re
import sys
from datetime import date
import unicodedata

try:
    from pybtex.database.input import bibtex
    from pybtex.exceptions import PybtexError
    from pybtex.richtext import Text
except ImportError:
    bibtex = None

    class PybtexError(Exception):
        pass


def plain_text(value):
    """Render BibTeX's LaTeX markup as HTML for publication pages."""
    return html.unescape(Text.from_latex(str(value)).render_as("html"))


def slugify(title):
    title = unicodedata.normalize("NFKD", title)
    slug = title.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "publication"


def publication_date(fields, entry_key):
    year = fields.get("year", "").strip()
    if not re.fullmatch(r"\d{4}", year):
        raise ValueError(f"entry {entry_key!r} needs a four-digit year")

    month_value = fields.get("month", "1").strip().strip("{}")
    month_names = {
        name: month
        for month, names in enumerate(
            (
                ("jan", "january"), ("feb", "february"), ("mar", "march"),
                ("apr", "april"), ("may",), ("jun", "june"),
                ("jul", "july"), ("aug", "august"), ("sep", "september"),
                ("oct", "october"), ("nov", "november"), ("dec", "december"),
            ),
            start=1,
        )
        for name in names
    }
    if month_value.lower() in month_names:
        month = month_names[month_value.lower()]
    else:
        try:
            month = int(month_value)
        except ValueError as error:
            raise ValueError(
                f"entry {entry_key!r} has an invalid month: {month_value!r}"
            ) from error

    day_value = fields.get("day", "1").strip().strip("{}")
    try:
        day = int(day_value)
        return date(int(year), month, day).isoformat()
    except ValueError as error:
        raise ValueError(
            f"entry {entry_key!r} has an invalid publication date"
        ) from error


def authors_for(entry):
    authors = entry.persons.get("author", [])
    rendered_authors = []
    for person in authors:
        first_names = person.first_names + person.middle_names
        last_names = person.prelast_names + person.last_names
        name = " ".join(first_names + last_names)
        if person.lineage_names:
            name += ", " + " ".join(person.lineage_names)
        rendered_authors.append(plain_text(name))
    return ", ".join(rendered_authors)


def category_for(entry_type):
    if entry_type.lower() == "book":
        return "books"
    if entry_type.lower() in {"inproceedings", "conference", "proceedings"}:
        return "conferences"
    return "manuscripts"


def publication_markdown(entry, entry_key):
    fields = entry.fields
    title = plain_text(fields.get("title", "")).strip()
    if not title:
        raise ValueError(f"entry {entry_key!r} has no title")

    pub_date = publication_date(fields, entry_key)
    venue = plain_text(
        fields.get("journal")
        or fields.get("booktitle")
        or fields.get("publisher")
        or fields.get("institution")
        or fields.get("howpublished")
        or ""
    ).strip()
    if not venue:
        raise ValueError(f"entry {entry_key!r} needs a journal, booktitle, or publisher")
    excerpt = plain_text(fields.get("abstract") or fields.get("note") or "").strip()
    paper_url = fields.get("url", "").strip()
    if not paper_url and fields.get("doi"):
        paper_url = "https://doi.org/" + fields["doi"].strip()

    citation_parts = []
    authors = authors_for(entry)
    if authors:
        citation_parts.append(authors + ".")
    citation_parts.extend((f"({pub_date[:4]}).", f'"{title}."'))
    if venue:
        venue_details = venue
        volume = fields.get("volume", "").strip()
        number = fields.get("number", "").strip()
        pages = fields.get("pages", "").strip()
        if volume:
            venue_details += f", {volume}"
            if number:
                venue_details += f"({number})"
        if pages:
            venue_details += f", pp. {pages}"
        citation_parts.append(venue_details + ".")
    citation = " ".join(citation_parts)

    basename = f"{pub_date}-{slugify(title)}"
    metadata = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        "collection: publications",
        f"category: {category_for(entry.type)}",
        f"permalink: /publication/{basename}",
    ]
    if excerpt:
        metadata.append(f"excerpt: {json.dumps(excerpt, ensure_ascii=False)}")
    metadata.extend(
        (
            f"date: {pub_date}",
            f"venue: {json.dumps(venue, ensure_ascii=False)}",
        )
    )
    if paper_url:
        metadata.append(f"paperurl: {json.dumps(paper_url, ensure_ascii=False)}")
    metadata.extend(
        (
            f"citation: {json.dumps(citation, ensure_ascii=False)}",
            "---",
        )
    )

    body = []
    if paper_url:
        body.append(f"[Download paper here]({paper_url})")
    if excerpt:
        body.append(excerpt)
    body.append(f"Recommended citation: {citation}")
    return basename + ".md", "\n".join(metadata) + "\n\n" + "\n\n".join(body) + "\n"


def input_files(paths):
    if paths:
        return paths

    print("Enter BibTeX file paths one at a time. Press Enter on a blank line when done.")
    paths = []
    while True:
        try:
            path = input("BibTeX file: ").strip()
        except EOFError:
            break
        if not path:
            break
        paths.append(path)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate AcademicPages publication pages from multiple BibTeX files."
    )
    parser.add_argument(
        "bib_files",
        nargs="*",
        help="BibTeX input files (omit to enter paths interactively)",
    )
    parser.add_argument(
        "--output-dir",
        help="directory for generated Markdown (default: repository _publications)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace publication pages that already exist",
    )
    args = parser.parse_args(argv)

    files = input_files(args.bib_files)
    if not files:
        parser.error("provide at least one BibTeX file")
    if bibtex is None:
        print(
            "Missing dependency: install it with "
            "`python3 -m pip install -r markdown_generator/requirements.txt`.",
            file=sys.stderr,
        )
        return 1

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = args.output_dir or os.path.join(script_dir, "..", "_publications")
    seen_keys = set()
    seen_files = set()
    created = skipped = errors = 0

    for path in files:
        try:
            bibdata = bibtex.Parser().parse_file(path)
        except (OSError, PybtexError) as error:
            print(f"ERROR: could not read {path}: {error}", file=sys.stderr)
            errors += 1
            continue

        for key, entry in bibdata.entries.items():
            if key in seen_keys:
                print(f"Skipping duplicate BibTeX entry {key!r} from {path}")
                skipped += 1
                continue
            seen_keys.add(key)

            try:
                filename, content = publication_markdown(entry, key)
            except ValueError as error:
                print(f"ERROR: {path}: {error}", file=sys.stderr)
                errors += 1
                continue

            if filename in seen_files:
                print(
                    f"ERROR: multiple entries produce {filename}; "
                    f"skipping entry {key!r}",
                    file=sys.stderr,
                )
                errors += 1
                continue
            seen_files.add(filename)

            output_path = os.path.join(output_dir, filename)
            if os.path.exists(output_path) and not args.overwrite:
                print(
                    f"Skipping existing file {output_path} "
                    "(pass --overwrite to replace it)"
                )
                skipped += 1
                continue

            try:
                os.makedirs(output_dir, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as output:
                    output.write(content)
            except OSError as error:
                print(f"ERROR: could not write {output_path}: {error}", file=sys.stderr)
                errors += 1
                continue

            print(f"Created: {output_path}")
            created += 1

    print(f"Done: {created} created, {skipped} skipped, {errors} error(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
