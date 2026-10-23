# GUI Visual Testing Guide

This document explains how to use the visual testing infrastructure to verify GUI workflows and catch layout issues.

## Overview

The visual testing system captures screenshots at each workflow state and validates widget geometry to catch:
- Label text overflow (text wider than widget)
- Widget overlaps (elements covering each other)
- Layout issues at minimum window size
- State machine transitions

## Running Visual Tests

```bash
# Run all visual tests
python -m pytest tests/test_gui_visual.py -v

# Run specific test class
python -m pytest tests/test_gui_visual.py::TestLabelOverflow -v

# Run with screenshot output
python -m pytest tests/test_gui_visual.py::TestFullWorkflow -v -s
```

## Test Categories

### 1. Layout Validation (`TestExtractTabLayout`)
- `test_no_widget_overlaps`: Checks that no visible layout siblings overlap
- `test_initial_state_layout`: Verifies the initial Extract tab state
- `test_video_loaded_state`: Verifies state after video loads
- `test_busy_state`: Verifies extraction in progress
- `test_completion_state`: Verifies post-extraction state
- `test_pdf_ready_state`: Verifies PDF completion state

### 2. Label Overflow Detection (`TestLabelOverflow`)
- `test_status_label_fits`: Status label with long text
- `test_page_badge_fits`: Page count badge
- `test_elapsed_label_fits`: Elapsed time display
- `test_button_labels_fit`: All action buttons

### 3. Config Tab Layout (`TestConfigTabLayout`)
- `test_basic_mode_layout`: Basic settings mode
- `test_advanced_mode_layout`: Advanced settings mode

### 4. Full Workflow (`TestFullWorkflow`)
- `test_complete_workflow_visual`: Captures 6 screenshots through the workflow

### 5. Minimum Window Size (`TestMinimumWindowSize`)
- `test_minimum_size_no_clipping`: Verifies critical widgets stay visible
- `test_minimum_size_uses_scroll`: Verifies the tab scrolls instead of overlapping

### 6. Custom Widgets (`TestCustomWidgets`)
- `test_crop_preview_widget`: CropPreviewWidget rendering
- `test_seek_bar_widget`: DualHandleSeekBar rendering

## Screenshot Output

Screenshots are saved to temporary directories during test runs. To preserve them:

```python
# In test code, use a fixed output directory
output_dir = Path("tests/visual_output")
screenshot = capture_widget(window, output_dir, "state_name")
```

## AI Agent Workflow

An AI agent can verify the GUI by:

1. **Run visual tests**:
   ```bash
   python -m pytest tests/test_gui_visual.py -v --tb=short
   ```

2. **Read failure messages**: Tests report exact pixel measurements
   ```
   Failed: Button 'Start Extraction' text (213px) wider than available space (160px)
   ```

3. **Analyze screenshots**: Read the saved PNG files to visually inspect issues

4. **Fix layout issues**: Adjust widget sizes, fonts, or layout constraints

5. **Re-run tests**: Verify fixes resolved the issues

## Example: Fixing Button Overflow

If `test_button_labels_fit` fails:

```python
# Current code (app_gui.py:2173)
self.extract_btn = QPushButton("Start Extraction")
self.extract_btn.setFixedWidth(160)  # Too narrow!

# Fix: Increase width or shorten text
self.extract_btn.setFixedWidth(220)  # Wider
# OR
self.extract_btn.setText("Extract")  # Shorter label
```

## Example: Fixing Page Badge Overflow

If `test_page_badge_fits` fails:

```python
# Current code (app_gui.py:2133)
self.page_badge.setFixedWidth(110)  # Too narrow for "Pages: 999"

# Fix: Increase width
self.page_badge.setFixedWidth(150)
```

## Adding New Visual Tests

```python
def test_my_new_feature(self, window, tmp_path):
    """Test my new feature's layout."""
    tab = window.extract_tab

    # Set up state
    tab.some_property = "value"
    tab._update_state()
    process_events()

    # Capture screenshot
    screenshot = capture_widget(window, tmp_path, "my_feature")

    # Assert visibility
    assert tab.my_widget.isVisible()

    # Assert no overflow
    metrics = tab.my_label.fontMetrics()
    text_width = metrics.horizontalAdvance(tab.my_label.text())
    if text_width > tab.my_label.width():
        pytest.fail(f"Label overflow: {text_width}px > {tab.my_label.width()}px")
```

## Integration with CI

Add to your CI pipeline:

```yaml
- name: Run visual tests
  run: python -m pytest tests/test_gui_visual.py -v --tb=short
```

## Known Issues

None. The Extract tab now scrolls its content when the window is too short,
while the action bar stays pinned at the bottom.

## Tips

- Use `process_events()` after state changes to ensure layout updates
- Test at minimum window size to catch responsive layout issues
- Capture screenshots at each state transition for visual regression tracking
- Use meaningful screenshot names for easy identification
