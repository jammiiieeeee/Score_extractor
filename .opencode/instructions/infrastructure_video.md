# Infrastructure: Video Specification

## Page Change Detection
- **Metric**: Structural Similarity Index (SSIM).
- **Region of Interest (ROI)**: Center 60% of the frame (ignores edge noise/UI).
- **Cooldown**: 1.5 seconds post-trigger to prevent multi-captures during a single turn.
- **Dual-Speed Skipping**:
    - **Seek Mode**: Check frame every 0.5s.
    - **Scan Mode**: On detection, check every 0.1s to find precise trigger.

## A/B Composite Strategy
1. **Frame A**: Captured at $T_{trigger}$.
2. **Frame B**: Captured at $T_{trigger} + 3.0$ seconds.
3. **Dynamic Bar Erase**:
    - Compute absolute difference $|Frame A - Frame B|$.
    - Vertical sum of differences to find the "playback bar" X-coordinate.
    - Overlay Frame B's left section (up to `bar_x + 10px`) onto Frame A.

## Buffer Management
- Maintain a **3-second circular buffer** (at video FPS).
- If video ends before 3s window is met for the final page, use the **last available frame** as Frame B.
