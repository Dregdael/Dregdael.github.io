# Markdown Generator

This directory contains various ways of creating Markdown for your site. In general, filenames that end with `.ipynb` or `.py` are similar, but may contain different documentation or are intended to be run from with GitHub when deploying your site.

## Python Scripts

The .py files are Python scripts that that can be run from the command line (ex., `python3 publications.py publications.csv`) with the objective of also ensuring that they have reduced requirements for packages, which may allow them to run when deploying your site from within GitHub.

### Generate publication pages from BibTeX

Install the BibTeX parser dependency:

```bash
python3 -m pip install -r markdown_generator/requirements.txt
```

Run the generator with one or more BibTeX files:

```bash
python3 markdown_generator/pubsFromBib.py files/papers.bib files/conference_papers.bib
```

If no input files are provided, the script prompts for file paths one at a time;
submit a blank line when finished. Generated pages go to `_publications/` by
default. Use `--output-dir PATH` to choose another destination. Existing pages
are left unchanged unless `--overwrite` is provided.

## Jupyter Notebooks

These .ipynb files are Jupyter notebook files that convert a TSV containing structured data about talks (`talks.tsv`) or presentations (`presentations.tsv`) into individual markdown files that will be properly formatted for the academicpages template. The notebooks contain a lot of documentation about the process.
