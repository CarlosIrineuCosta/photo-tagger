# Recovery and Error Handling

This document outlines how to handle common error scenarios and recover from interrupted processing runs.

## File Processing States

The system uses a state model to track the processing status of each file. This allows for more efficient and resumable processing. The primary states are:

-   **`new`**: The file has been detected by the scanner for the first time. It needs to be fully processed (thumbnail generation, embedding, scoring).
-   **`modified`**: The file has been modified since the last run (based on its modification time). It needs to be fully re-processed.
-   **`unchanged`**: The file has not changed since the last run. The system can skip expensive processing steps for these files and reuse cached data.
-   **`blocked`**: The file is skipped due to a blocking condition (e.g., it's a TIFF file that is too large).

This state is determined during the `scan` phase and is used by subsequent steps to optimize the pipeline.

## Interrupted Processing

The photo-tagger pipeline is designed to be resumable. The CLI is composed of several discrete commands (`scan`, `thumbs`, `embed`, `score`, etc.) that each read the output of the previous step and write their own results to the run directory (`runs/<run_id>/`).

The caching mechanism that determines the file status (`new`, `modified`, `unchanged`) is key to this resilience. If a run is interrupted, the cache (`.tagger_cache.json` in the root of the scanned directory) may not be up-to-date. However, the next run will correctly identify which files need processing.

**Recovery Steps:**
1.  Simply re-run the command that was interrupted (e.g., `python -m app.cli.tagger run ...`).
2.  The scanner will automatically detect the state of each file and ensure that only necessary processing is performed. For example, if the `embed` step was interrupted, the next run will find that thumbnails are already generated and will proceed directly to the embedding step for `new` and `modified` files.

## Blocked and Skipped Files

Certain files may be skipped during processing. This is usually due to file format limitations or potential for causing system instability.

### Large TIFF Files

- **Scenario**: The scanner will skip any TIFF files (`.tif`, `.tiff`) that are larger than 1GB.
- **Reason**: Processing very large TIFF files can consume a large amount of memory and cause the application to crash.
- **Indication**: These files will not appear in the output of the `scan` command and will be silently skipped. Their status can be considered `blocked`.

### Corrupt Image Files

- **Scenario**: An image file may be corrupt and cannot be read by the processing libraries (`Pillow` or `rawpy`).
- **Reason**: File corruption can occur for many reasons, including disk errors or incomplete file transfers.
- **Indication**: The application will likely raise an error and stop processing when it encounters a corrupt file. The error message in the console will typically indicate the path to the problematic file.
- **Recovery**: 
    1. Remove or repair the corrupt file.
    2. Re-run the interrupted command.

## Checking Logs

For any unexpected behavior, the first place to look for information is the log file located at `runs/<run_id>/log.txt`. This file contains timestamps and messages for each major step of the pipeline, which can help you diagnose at what point an error occurred.