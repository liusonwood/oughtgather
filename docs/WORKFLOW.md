# Oughtgather Technical Workflow

This document outlines the detailed operational flow and architectural interactions of the oughtgather project.

## High-Level Workflow Diagram

```text
[Config (config.json)]
       |
       v
+-------------------------+
|      src/main.py        | <--- Orchestrator (Main Loop)
+------------+------------+
             |
             | 1. fetch()
             v
+-------------------------+    +------------------+
|    Fetchers (Base)      |--->|   FetchResult    |
+------------+------------+    +------------------+
             |
             | 2. check_new()
             v
+-------------------------+
|      DedupTracker       |
+------------+------------+
             |
             | 3. process()
             v
+-------------------------+    +------------------+
| Content/Image Processors|--->|   Sanitized      |
+------------+------------+    |     Content      |
             |                 +------------------+
             | 4. generate()
             v
+-------------------------+
|     EPUBGenerator       |
+------------+------------+
             |
             | 5. upload()
             v
+-------------------------+
| Uploader (SMTP/WebDAV)  |
+-------------------------+
```

## Detailed Component Interactions

### 1. Configuration (`src/config.py`)
- Loaded at initialization via `config.json`.
- Dictates which fetchers are enabled and their respective settings (URLs, API keys, credentials).

### 2. Fetching (`src/fetchers/`)
- All fetchers implement `BaseFetcher`.
- The `main` orchestrator calls `.fetch()` on enabled fetchers.
- Returns a standardized `FetchResult` object containing:
    - Raw content (HTML/Text).
    - Metadata (Title, Author, Date, Source URL).
    - Potential list of images/assets.

### 3. Deduplication (`src/dedup/`)
- `DedupTracker` maintains a persistent store of processed content hashes (or unique identifiers).
- Before processing, `main` checks the `FetchResult` against this tracker. Only new items proceed.

### 4. Processing (`src/processors/`)
- **ContentProcessor**: Sanitizes HTML, applies style rules, wraps emoji if necessary (via `NotoEmoji-Regular.ttf`), and flattens nested structures.
- **ImageProcessor**: Downloads images, resizes, optimizes formats, and maps them locally within the EPUB structure.

### 5. EPUB Generation (`src/epub/`)
- `EPUBGenerator` takes the list of processed `FetchResult` objects.
- Orchestrates:
    - `cover.py`: Generates the cover image if not provided.
    - `toc.py`: Builds the Table of Contents (NCX/NAV).
    - Assembles the OPF and standard EPUB structure.

### 6. Uploading (`src/uploader/`)
- Final assembly is passed to the configured Uploader (e.g., `SMTPSender` for Kindle email, or `WebDAVUploader`).

## Key Data Objects

| Object | Purpose |
| :--- | :--- |
| `FetchResult` | The standardized container for raw content fetched from any source. |
| `Config` | The parsed configuration settings from `config.json`. |
| `DedupStore` | Persistent storage (managed by `DedupTracker`) of processed item identifiers. |

## Error Handling
- Each stage is wrapped in try-except blocks within `main.py`.
- Failures in a single fetcher do not halt the entire process.
- Errors are logged via `src/utils/logger.py` for auditability.
