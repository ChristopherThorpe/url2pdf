#!/usr/bin/env python3
"""
Web to PDF Converter

This script accepts a URL to a web page and saves it as a PDF with high fidelity.
The PDF includes a header with the URL and timestamp when the page was fetched.
"""

import os
import asyncio
import datetime
import tempfile
from urllib.parse import urlparse
import click
from playwright.async_api import async_playwright
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from PyPDF2 import PdfWriter, PdfReader


async def capture_webpage(url, output_path, viewport_width=1280, viewport_height=800):
    """
    Capture a webpage and save it as PDF using Playwright.
    
    Args:
        url: The URL of the webpage to capture
        output_path: Path where the PDF will be saved
        viewport_width: Width of the browser viewport
        viewport_height: Height of the browser viewport
    """
    async with async_playwright() as p:
        # Create a browser with ad blocker
        browser = await p.chromium.launch()
        
        # Create a context with the ad blocker enabled
        context = await browser.new_context(
            viewport={'width': viewport_width, 'height': viewport_height},
            # Enable JavaScript to run our scripts
            java_script_enabled=True
        )
        
        # Install ad blocker by loading uBlock Origin
        try:
            # Create a temporary directory for the extension
            with tempfile.TemporaryDirectory() as extension_path:
                # Install uBlock Origin extension (this is a simplified version)
                print("Setting up ad blocker...")
                # We'll use JavaScript to block ads instead
                await context.add_init_script("""
                    // Simple ad blocker script
                    window.addEventListener('DOMContentLoaded', () => {
                        // Common ad selectors
                        const adSelectors = [
                            'div[id*="google_ads"]',
                            'div[id*="ad-"]',
                            'div[class*="ad-"]',
                            'div[class*="ads-"]',
                            'div[id*="banner"]',
                            'iframe[src*="doubleclick"]',
                            'iframe[src*="ad"]',
                            'iframe[id*="google_ads"]',
                            'ins.adsbygoogle',
                            '[class*="banner-ad"]',
                            '[id*="banner-ad"]',
                            '[class*="sponsored"]',
                            '[id*="sponsored"]'
                        ];
                        
                        // Remove ad elements
                        adSelectors.forEach(selector => {
                            document.querySelectorAll(selector).forEach(el => {
                                if (el) el.remove();
                            });
                        });
                    });
                """);
        except Exception as e:
            print(f"Warning: Failed to set up ad blocker: {e}")
        
        page = await context.new_page()
        
        try:
            # Navigate to the URL
            print(f"Navigating to {url}...")
            await page.goto(url, wait_until='networkidle', timeout=60000)
            
            # Wait a bit for any dynamic content to load
            await page.wait_for_timeout(3000)
            
            # Resize large images and remove persistent headers
            print("Processing page content...")
            await page.evaluate("""() => {
                // Resize large images
                const viewportWidth = window.innerWidth;
                const maxWidth = viewportWidth * 0.33; // 33% of viewport width
                
                document.querySelectorAll('img').forEach(img => {
                    if (img.width > maxWidth) {
                        // Save original dimensions as data attributes
                        img.dataset.originalWidth = img.width;
                        img.dataset.originalHeight = img.height;
                        
                        // Calculate new dimensions maintaining aspect ratio
                        const aspectRatio = img.width / img.height;
                        const newWidth = maxWidth;
                        const newHeight = newWidth / aspectRatio;
                        
                        // Apply new dimensions
                        img.style.width = newWidth + 'px';
                        img.style.height = newHeight + 'px';
                    }
                });
                
                // Identify and mark potential persistent headers
                // We'll look for elements that are likely to be headers
                const potentialHeaders = document.querySelectorAll('header, nav, .header, #header, [class*="header"], [class*="nav"], [id*="nav"], [class*="menu"], [id*="menu"]');
                
                potentialHeaders.forEach(header => {
                    if (header.getBoundingClientRect().top < 100) {
                        // Mark header elements with a data attribute
                        header.dataset.persistentHeader = 'true';
                    }
                });
            }""")
            
            # Ensure images are loaded
            print("Waiting for images to load...")
            await page.wait_for_load_state('networkidle')
            
            # Additional wait for any lazy-loaded images
            await page.evaluate("""() => {
                return new Promise((resolve) => {
                    const images = document.querySelectorAll('img');
                    let loaded = 0;
                    
                    if (images.length === 0) {
                        resolve();
                        return;
                    }
                    
                    images.forEach(img => {
                        if (img.complete) {
                            loaded++;
                            if (loaded === images.length) resolve();
                        } else {
                            img.addEventListener('load', () => {
                                loaded++;
                                if (loaded === images.length) resolve();
                            });
                            img.addEventListener('error', () => {
                                loaded++;
                                if (loaded === images.length) resolve();
                            });
                        }
                    });
                });
            }""")
            
            # Create a modified CSS to hide persistent headers on print
            await page.add_style_tag(content="""
                @media print {
                    [data-persistent-header="true"] {
                        display: none !important;
                    }
                    
                    /* Make sure the first page still shows the header */
                    @page:first {
                        [data-persistent-header="true"] {
                            display: block !important;
                        }
                    }
                }
            """)
            
            # Save the page as PDF with margins
            print("Generating PDF...")
            await page.pdf(
                path=output_path,
                format='Letter',
                margin={
                    'top': '0.75in',
                    'right': '0.75in',
                    'bottom': '0.75in',
                    'left': '0.75in'
                },
                print_background=True
            )
            
        finally:
            await browser.close()
            
    return output_path


def add_header_footer(input_pdf, output_pdf, url, timestamp):
    """
    Add a header with URL and timestamp to each page of the PDF,
    and a page number in the footer.
    
    Args:
        input_pdf: Path to the input PDF file
        output_pdf: Path to save the output PDF file
        url: The URL of the webpage
        timestamp: The timestamp when the webpage was fetched
    """
    # Read the original PDF
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    
    # Process each page
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        page_width, page_height = letter  # Default letter size
        
        # Create a PDF with the header and footer
        overlay_pdf = f"overlay_{page_num}.pdf"
        c = canvas.Canvas(overlay_pdf, pagesize=letter)
        
        # Add the URL and timestamp as header (in the top margin)
        c.setFont("Helvetica", 8)
        c.drawString(0.5 * inch, page_height - 0.5 * inch, f"URL: {url}")
        c.drawString(0.5 * inch, page_height - 0.65 * inch, f"Fetched: {timestamp}")
        
        # Add a thin line to separate header from content
        c.setLineWidth(0.5)
        c.line(0.5 * inch, page_height - 0.7 * inch, page_width - 0.5 * inch, page_height - 0.7 * inch)
        
        # Add page number in the footer (lower right corner)
        c.drawString(page_width - 1.0 * inch, 0.5 * inch, f"Page {page_num + 1} of {len(reader.pages)}")
        
        c.save()
        
        # Merge the overlay with the original page
        overlay_reader = PdfReader(overlay_pdf)
        overlay_page = overlay_reader.pages[0]
        
        # Overlay the header/footer onto the original page
        page.merge_page(overlay_page)
        writer.add_page(page)
        
        # Clean up the temporary overlay PDF
        os.remove(overlay_pdf)
    
    # Save the output PDF
    with open(output_pdf, "wb") as f:
        writer.write(f)
    
    return output_pdf


@click.command()
@click.argument('url')
@click.option('--output', '-o', default=None, help='Output PDF file path')
@click.option('--width', '-w', default=1280, help='Viewport width in pixels')
@click.option('--height', '-h', default=800, help='Viewport height in pixels')
def main(url, output, width, height):
    """Convert a web page to PDF with high fidelity."""
    # Generate default output filename if not provided
    if not output:
        domain = urlparse(url).netloc
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"{domain}_{timestamp_str}.pdf"
    
    # Get the current timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create a temporary PDF
    temp_pdf = f"temp_{os.path.basename(output)}"
    
    try:
        # Convert webpage to PDF
        print(f"Capturing webpage: {url}")
        asyncio.run(capture_webpage(url, temp_pdf, width, height))
        
        # Add header and footer to the PDF
        print("Adding headers, footers, and page numbers...")
        add_header_footer(temp_pdf, output, url, timestamp)
        
        print(f"PDF saved to: {output}")
    finally:
        # Clean up the temporary PDF
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)


if __name__ == "__main__":
    main()
