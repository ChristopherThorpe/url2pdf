# Web to PDF Converter

A Python tool that converts web pages to PDF format with high fidelity, preserving the appearance as seen in a browser. The PDF includes a header with the URL and timestamp when the page was fetched.

## Features

- Captures web pages with high fidelity using Playwright (Chromium)
- Maintains the visual appearance of the web page
- Adds a header to each page with URL and timestamp
- Configurable viewport dimensions
- Simple command-line interface

## Installation

1. Clone or download this repository
2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Install the Playwright browsers:

```bash
playwright install
```

## Usage

Basic usage:

```bash
python web_to_pdf.py https://example.com
```

With custom output path:

```bash
python web_to_pdf.py https://example.com -o example.pdf
```

With custom viewport dimensions:

```bash
python web_to_pdf.py https://example.com -w 1920 -h 1080
```

### Options

- `--output`, `-o`: Specify the output PDF file path (default: domain_timestamp.pdf)
- `--width`, `-w`: Specify the viewport width in pixels (default: 1280)
- `--height`, `-h`: Specify the viewport height in pixels (default: 800)

## How It Works

1. Uses Playwright to load and render the web page with a Chromium browser
2. Captures the page as a PDF
3. Adds a header to each page with the URL and timestamp using ReportLab and PyPDF2
4. Saves the final PDF to the specified location

## Requirements

- Python 3.7+
- Playwright
- ReportLab
- PyPDF2
- Click
