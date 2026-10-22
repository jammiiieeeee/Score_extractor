# Handoff: after #12

## Where things stand

Branch `refactor/unified-page-model`. Latest commit `ecf86d8` (ticket #12) is
pushed to `origin`.

Parent migration: #8. Sequence so far:

| Ticket | Title | State |
|--------|-------|-------|
| #9  | One copy of each page | done |
| #10 | A page knows its own boundary row, file and status | done |
| #12 | Page state is read and changed through one interface | done (this branch) |
| #11 | The PDF is built from pages, and the crop rule lives in one place | **NEXT** |
| #13 | Removing, reordering and reloading pages no longer desync | after #11 |

#11 is now unblocked (it was blocked by #10). #13 is blocked by both #11 and
#12, so #13 comes after #11.

## What #12 left behind (what you can build on)

- `PageStore` (`src/domain/page_store.py`) now holds `Page` objects, not
  `Frame`s. Each `Page` carries `image`, `boundary_row`, `attempt_number`,
  `file`, `status`.
- `PageState` read view added in `src/domain/models.py`.
- Public page interface on `GuiApi` (`src/api/gui_api.py`, Page Management
  section):
  - `get_page(index) -> PageState`
  - `set_page_status(index, status)`
  - `add_page(image, boundary_row, file, status) -> int`
  - `set_pages(pages)`
  - plus the existing `get_page_count / get_page_thumbnail / get_page_full /
    remove_page / reorder_pages / clear_pages`
- Extraction feeds the store from `result.page_records`
  (`src/api/gui_api.py`, `_run_extraction`).
- `_current_crop_rows()` now derives the rows straight from the pages
  (`[p.boundary_row for p in self._pages.all_pages()]`).
  `_page_crop_rows` is a legacy mirror refreshed by `_sync_crop_rows()` — it is
  removed in #13, do not add new readers of it.

## Ticket #11 in one line

Move the PDF builder onto page objects, and move the crop rule into one
reusable function any consumer can call (the PDF today, a page preview later).
Output must be identical: same pages, same order, same crop.

## Where the crop rule lives today (the thing to extract)

The single crop decision is inside
`PdfService.create_pdf()` (`src/infrastructure/pdf_service.py`, the `if/elif`
block over `mode = config.boundary_mode`). It computes `y_end` per page from:

- `mode == "off"`  -> full frame (`y_end = img_h`)
- `mode == "auto"` -> `boundary_row - boundary_offset_px` when a row exists,
  else `img_h * default_crop_ratio`
- otherwise (manual/legacy) -> `img_h * default_crop_ratio`

Inputs: the page's image, its `boundary_row`, `config.boundary_offset_px`,
`config.default_crop_ratio`, `config.boundary_mode`. Nothing else.

Suggested shape (adjust to taste, keep it pure and importable without the PDF):

```python
def crop_end_row(image, boundary_row, config) -> int:
    ...
```

The PDF builder should call it; a page preview should be able to call the same
function and get the identical crop.

## Interface to change

`IPdfService.create_pdf()` in `src/domain/interfaces.py` currently takes
`images: List[np.ndarray]` plus a separate `crop_rows: List[Optional[int]]`.
#11 asks that it receive **pages** instead of two parallel lists.

Callers to update (`rg "create_pdf"`):
- `PdfService.create_pdf` implementation
  (`src/infrastructure/pdf_service.py:15`).
- `IPdfService.create_pdf` signature (`src/domain/interfaces.py:123`).
- `GuiApi._run_generate_pdf` (`src/api/gui_api.py:659`) — passes
  `self._pages.all_images()` + `self._current_crop_rows()`. After #11 it should
  pass the pages (e.g. `self._pages.all_pages()`), and `_current_crop_rows`
  may become unused by the PDF path.
- `GeneratePdfUseCase.execute` (`src/application/use_cases.py:204`) — passes
  frame images; update or retire. Its tests are in `tests/test_use_cases.py`
  (`TestGeneratePdfUseCase`).
- CLI: `main.py:84` and `main.py:170` both call `pdf_service.create_pdf(...)`.
- Fake service in `tests/conftest.py:335` mirrors the signature.

## Tests to touch (keep the contracts)

Crop/PDF contract tests:
- `tests/test_pdf_service.py` — many tests call
  `create_pdf(images, out, config, title_hint=..., crop_rows=[...])` through
  the `_capture_drawn_heights` helper. These move to the page-based signature
  and/or call the new crop function directly.
- `tests/test_double_crop_bug.py` — asserts the single-crop model; update the
  call signature.
- Add a test proving "a page cropped by the crop function is cropped
  identically to the same page as drawn by the PDF" (an explicit #11 AC).

## Acceptance criteria for #11 (from the ticket)

- [ ] The PDF builder receives pages, not an image list plus a crop-row list.
- [ ] The crop end for a page is computed by one function callable without the
      PDF path.
- [ ] A page cropped by that function is cropped identically to the same page
      drawn by the PDF.
- [ ] The generated PDF contains the same pages, same order, same crop, as
      before.
- [ ] The full test suite passes.

## Commands

```
python -m pytest tests/ -q -m "not slow"        # fast suite
python -m pytest tests/ -q -m "slow"            # extraction e2e
python -m pytest tests/ -q                       # everything
```

## Known pre-existing failures (NOT caused by you)

`tests/test_gui_visual.py` has 3 failing tests on this branch before any change:
`TestExtractTabLayout::test_no_widget_overlaps`,
`TestExtractTabLayout::test_welcome_state_layout`,
`TestCustomWidgets::test_welcome_widget` — all reference a missing
`ExtractTab.welcome_widget`. Ignore unless you touch the welcome widget.

## Gotchas

- Windows-only repo. Use ASCII in code comments where possible; several files
  already contain mojibake box-drawing separators, don't try to "fix" them.
- Do not commit without explicit permission (see root `AGENTS.md`).
- Commit attribution must include
  `Co-Authored-By: opencode <noreply@opencode.ai>`.
- `_page_crop_rows` and the store's old parallel lists are intentionally still
  present; #13 deletes them. Don't delete them early unless you're also doing
  #13.
