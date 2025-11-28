# Paper Downloader

A Python script to automatically download academic papers (PDFs) based on a BibTeX reference file.

## Features

- **BibTeX Parsing**: Reads citations from a `.bib` file.
- **Auto-Discovery**:
  - Extracts URLs directly from BibTeX entries (e.g., ArXiv links).
  - Uses **Google Custom Search API** to find PDFs for entries without direct links.
- **Concurrent Downloading**: Fast downloads using multi-threading.
- **Smart Handling**:
  - Skips already downloaded files.
  - Sanitizes filenames from titles.
  - Generates a failure report (`download_report.txt`) for manual review.

## Prerequisites

- Python 3.x
- Required Python packages:
  ```bash
  pip install bibtexparser requests
  ```

## Configuration

Open `main.py` and modify the **CONFIGURATION** section at the top:

1.  **BibTeX File**:
    Change `BIB_FILE` to match your `.bib` filename (e.g., `'DeMoE.bib'`).
    ```python
    BIB_FILE = 'references.bib'
    ```

2.  **Google Search API** (Required for automatic PDF searching):
    You need to set up a Google Custom Search Engine to find papers that don't have direct URLs in the BibTeX.
    *   **API Key**: Get it from the [Google Developers Console](https://developers.google.com/custom-search/v1/introduction).
    *   **Search Engine ID (CX)**: Create one at [Google Programmable Search Engine](https://cse.google.com/cse/all).
    
    Update the variables in `main.py`:
    ```python
    GOOGLE_API_KEY = "YOUR_GOOGLE_API_KEY_HERE"
    GOOGLE_CSE_ID = "YOUR_SEARCH_ENGINE_ID_HERE"
    ```

## Usage

1.  Place your `.bib` file in the project directory.
2.  Run the script:
    ```bash
    python main.py
    ```
3.  Papers will be downloaded to the `downloaded_papers/` directory.
4.  Check `download_report.txt` for any papers that failed to download.

## Output

- **`downloaded_papers/`**: Directory containing the downloaded PDF files.
- **`download_report.txt`**: A detailed report of failed downloads, including reasons and fallback links (like DOIs) for manual retrieval.
