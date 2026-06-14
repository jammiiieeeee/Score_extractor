# System & Safety Specification

## UUID Sandbox Protocol
1.  **Creation**: Generate `sandbox_id = uuid.uuid4()`.
2.  **Path**: Create folder `./tmp_{sandbox_id}/`.
3.  **Operations**: 
    - All `cv2.imwrite` and `cv2.imread` must target this folder using ASCII filenames (e.g., `frame_001.png`).
    - The draft PDF is generated inside this folder.
4.  **Resource Release**: 
    - Explicitly call `cap.release()` for video.
    - Close the PDF object.
    - (If debug is OFF) Prepare for cleanup.

## Windows Unicode Safety
- Source paths (Input Video) are handled via Python `pathlib` or `os` which are Unicode-aware.
- Destination paths (Output PDF) are handled via `shutil.move()` after the file handle is closed.
- **Error Handling**: If `shutil.move` fails because of a lock (PermissionError), the system MUST:
    1. Show a CLI prompt: *"Target file is locked. Please close the PDF and press ENTER to retry."*
    2. Retry the move.

## Cleanup
- If `debug=False`, delete the UUID folder only AFTER successful move.
- If `debug=True`, keep the folder and print the path to console.
