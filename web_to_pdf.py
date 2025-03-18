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


async def capture_webpage(url, output_path, viewport_width=1280, viewport_height=800, scale=100):
    """
    Capture a webpage and save it as PDF using Playwright.
    
    Args:
        url: The URL of the webpage to capture
        output_path: Path where the PDF will be saved
        viewport_width: Width of the browser viewport
        viewport_height: Height of the browser viewport
        scale: Percentage scale for the content (100 = full size)
    """
    # Apply scaling to viewport dimensions
    scaled_viewport_width = int(viewport_width * scale / 100)
    scaled_viewport_height = int(viewport_height * scale / 100)
    
    # Create first page PDF and rest pages PDF
    first_page_pdf = f"first_page_{os.path.basename(output_path)}"
    rest_pages_pdf = f"rest_pages_{os.path.basename(output_path)}"
    
    async with async_playwright() as p:
        # Create a browser with ad blocker
        browser = await p.chromium.launch()
        
        # Set up a modern Chrome user agent
        desktop_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        headers = {
            'User-Agent': desktop_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Create a single context with the user agent
        context = await browser.new_context(
            viewport={'width': scaled_viewport_width, 'height': scaled_viewport_height},
            java_script_enabled=True,
            user_agent=desktop_user_agent,
            extra_http_headers=headers
        )
        
        # Create a page to fetch the content
        fetch_page = await context.new_page()
        
        # Navigate to the URL and cache the content
        print(f"Fetching content from {url}...")
        await fetch_page.goto(url, wait_until='networkidle', timeout=60000)
        
        # Get the cached HTML content
        cached_content = await fetch_page.content()
        
        # Create two pages from the cached content
        first_page = await context.new_page()
        rest_pages = await context.new_page()
        
        # Set the cached content on both pages
        await first_page.set_content(cached_content)
        await rest_pages.set_content(cached_content)
        
        # Close the fetch page as we no longer need it
        await fetch_page.close()
        
        try:
            # Install ad blocker by loading uBlock Origin
            try:
                # Create a temporary directory for the extension
                with tempfile.TemporaryDirectory() as extension_path:
                    # Install uBlock Origin extension (this is a simplified version)
                    print("Setting up ad blocker...")
                    # We'll use JavaScript to block ads instead
                    ad_block_script = """
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
                    """
                    
                    await first_page.add_init_script(ad_block_script)
                    await rest_pages.add_init_script(ad_block_script)
            except Exception as e:
                print(f"Warning: Failed to set up ad blocker: {e}")
            
            # Enhanced cookie popup removal with compatible selectors
            remove_popups_js = """() => {
                // Common cookie popup selectors
                const cookieSelectors = [
                    // Common classes and IDs
                    '.cookie-banner', '#cookie-banner',
                    '.cookie-notice', '#cookie-notice',
                    '.cookie-consent', '#cookie-consent',
                    '.cookie-policy', '#cookie-policy',
                    '.cookie-modal', '#cookie-modal',
                    '.gdpr', '#gdpr',
                    '.privacy-alert', '#privacy-alert',
                    
                    // Position-based detection for bottom elements
                    'div[style*="bottom: 0"]',
                    'div[style*="position: fixed"][style*="bottom"]',
                    'div[style*="z-index"][style*="position: fixed"]',
                    
                    // Generic elements that might be popups
                    '.modal', '#modal',
                    '.popup', '#popup',
                    '.overlay', '#overlay'
                ];
                
                // Remove elements matching selectors
                cookieSelectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        // Check if position is fixed or absolute
                        const style = window.getComputedStyle(el);
                        if (style.position === 'fixed' || style.position === 'absolute') {
                            // Check text content
                            const text = el.textContent.toLowerCase();
                            if (text.includes('cookie') || 
                                text.includes('consent') || 
                                text.includes('privacy') ||
                                text.includes('gdpr') ||
                                el.classList.contains('cookie') ||
                                el.id.includes('cookie')) {
                                el.remove();
                            }
                        }
                    });
                });
            }"""
            
            # Remove popups from both contexts
            await first_page.evaluate(remove_popups_js)
            await rest_pages.evaluate(remove_popups_js)
            
            # Wait a bit for any dynamic content to load
            await first_page.wait_for_timeout(3000)
            await rest_pages.wait_for_timeout(3000)
            
            # Ensure images are loaded on both pages
            print("Waiting for images to load...")
            await first_page.wait_for_load_state('networkidle')
            await rest_pages.wait_for_load_state('networkidle')
            
            # Process images and identify headers on the first page
            await first_page.evaluate("""() => {
                // Resize large images
                const viewportWidth = window.innerWidth;
                const maxWidth = viewportWidth * 0.33; // 33% of viewport width
                
                document.querySelectorAll('img').forEach(img => {
                    const computedStyle = window.getComputedStyle(img);
                    let width = img.width || parseInt(computedStyle.width);
                    
                    if (width > maxWidth) {
                        // Save original dimensions
                        img.dataset.originalWidth = width;
                        img.dataset.originalHeight = img.height || parseInt(computedStyle.height);
                        
                        // Calculate new dimensions maintaining aspect ratio
                        const aspectRatio = width / (img.height || parseInt(computedStyle.height) || width);
                        const newWidth = maxWidth;
                        const newHeight = newWidth / aspectRatio;
                        
                        // Apply new dimensions
                        img.style.width = newWidth + 'px';
                        img.style.height = newHeight + 'px';
                        img.style.maxWidth = '100%';
                    }
                });
            }""")
            
            # Apply similar image resizing to rest_pages
            await rest_pages.evaluate("""() => {
                // Resize large images
                const viewportWidth = window.innerWidth;
                const maxWidth = viewportWidth * 0.33; // 33% of viewport width
                
                document.querySelectorAll('img').forEach(img => {
                    const computedStyle = window.getComputedStyle(img);
                    let width = img.width || parseInt(computedStyle.width);
                    
                    if (width > maxWidth) {
                        // Save original dimensions
                        img.dataset.originalWidth = width;
                        img.dataset.originalHeight = img.height || parseInt(computedStyle.height);
                        
                        // Calculate new dimensions maintaining aspect ratio
                        const aspectRatio = width / (img.height || parseInt(computedStyle.height) || width);
                        const newWidth = maxWidth;
                        const newHeight = newWidth / aspectRatio;
                        
                        // Apply new dimensions
                        img.style.width = newWidth + 'px';
                        img.style.height = newHeight + 'px';
                        img.style.maxWidth = '100%';
                    }
                });
            }""")
            
            # Identify and preserve headers on first page only
            await first_page.evaluate("""() => {
                // Find potential header elements
                const potentialHeaders = [
                    'header', '.header', '#header',
                    'nav', '.nav', '#nav',
                    '.navbar', '#navbar',
                    '.site-header', '#site-header',
                    '.page-header', '#page-header',
                    '.main-header', '#main-header'
                ];
                
                // Mark headers for keeping
                potentialHeaders.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        const rect = el.getBoundingClientRect();
                        if (rect.top < 100) {
                            el.dataset.header = 'preserve';
                        }
                    });
                });
            }""")
            
            # Hide headers on rest_pages
            await rest_pages.evaluate("""() => {
                // Find potential header elements
                const potentialHeaders = [
                    'header', '.header', '#header',
                    'nav', '.nav', '#nav',
                    '.navbar', '#navbar',
                    '.site-header', '#site-header',
                    '.page-header', '#page-header',
                    '.main-header', '#main-header'
                ];
                
                // Hide headers
                potentialHeaders.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        const rect = el.getBoundingClientRect();
                        if (rect.top < 100) {
                            el.style.display = 'none';
                        }
                    });
                });
            }""")
            
            # Generate PDFs from both pages
            print("Generating first page PDF...")
            await first_page.pdf(
                path=first_page_pdf,
                format='Letter',
                margin={
                    'top': '0.75in',
                    'right': '0.75in',
                    'bottom': '0.75in',
                    'left': '0.75in'
                },
                scale=scale/100,
                print_background=True
            )
            
            print("Generating remaining pages PDF...")
            await rest_pages.pdf(
                path=rest_pages_pdf,
                format='Letter',
                margin={
                    'top': '0.75in',
                    'right': '0.75in',
                    'bottom': '0.75in',
                    'left': '0.75in'
                },
                scale=scale/100,
                print_background=True
            )
            
        finally:
            await browser.close()
    
    # Merge the PDFs
    print("Merging PDFs...")
    merged_pdf = merge_pdfs(first_page_pdf, rest_pages_pdf, output_path)
    
    # Clean up temporary files
    if os.path.exists(first_page_pdf):
        os.remove(first_page_pdf)
    if os.path.exists(rest_pages_pdf):
        os.remove(rest_pages_pdf)
    
    return merged_pdf


def merge_pdfs(first_page_pdf, rest_pages_pdf, output_path):
    """
    Merge the first page PDF with the rest of the pages PDF.
    
    Args:
        first_page_pdf: Path to the PDF containing only the first page
        rest_pages_pdf: Path to the PDF containing the rest of the pages
        output_path: Path where the merged PDF will be saved
    """
    writer = PdfWriter()
    
    # Add the first page from first_page_pdf
    if os.path.exists(first_page_pdf):
        first_reader = PdfReader(first_page_pdf)
        if len(first_reader.pages) > 0:
            writer.add_page(first_reader.pages[0])
    
    # Add the rest of the pages from rest_pages_pdf (skip the first page)
    if os.path.exists(rest_pages_pdf):
        rest_reader = PdfReader(rest_pages_pdf)
        # Skip the first page of rest_pages as it would be duplicate
        for page_num in range(1, len(rest_reader.pages)):
            writer.add_page(rest_reader.pages[page_num])
    
    # Write the merged PDF
    with open(output_path, "wb") as f:
        writer.write(f)
    
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
@click.option('--scale', '-s', default=100, help='Percentage scale for the content (100 = full size)')
def main(url, output, width, height, scale):
    """Convert a web page to PDF with high fidelity."""
    # Validate scale value
    if not (10 <= scale <= 200):
        raise click.BadParameter("Scale must be between 10 and 200")
    
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
        asyncio.run(capture_webpage(url, temp_pdf, width, height, scale))
        
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
