"""AI Agent Helper for GUI Visual Verification.

This script provides a programmatic interface for AI agents to:
1. Run visual tests and capture results
2. Analyze screenshots for layout issues
3. Generate reports of detected problems

Usage:
    python tests/ai_visual_helper.py [--output-dir DIR] [--analyze]
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_visual_tests(output_dir: Path = None, verbose: bool = True) -> Dict[str, Any]:
    """Run visual tests and return structured results.

    Args:
        output_dir: Directory to save screenshots (default: temp)
        verbose: Print test output

    Returns:
        Dict with test results, failures, and screenshot paths
    """
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_gui_visual.py",
        "-v",
        "--tb=short",
        "-s"
    ]

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent
    )

    if verbose:
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

    # Parse results
    lines = result.stdout.split('\n')
    passed = sum(1 for line in lines if 'PASSED' in line)
    failed = sum(1 for line in lines if 'FAILED' in line)

    failures = []
    for line in lines:
        if 'FAILED' in line or 'Failed:' in line:
            failures.append(line.strip())

    return {
        "exit_code": result.returncode,
        "passed": passed,
        "failed": failed,
        "total": passed + failed,
        "failures": failures,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def analyze_layout_issues(test_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse test failures to extract layout issues.

    Args:
        test_results: Output from run_visual_tests()

    Returns:
        List of detected issues with details
    """
    issues = []

    for failure in test_results["failures"]:
        # Parse overflow issues
        if "wider than" in failure:
            # Example: "Button 'Start Extraction' text (213px) wider than available space (160px)"
            import re
            match = re.search(r"(\w+).*?\((\d+)px\).*?(\w+).*?\((\d+)px\)", failure)
            if match:
                issues.append({
                    "type": "overflow",
                    "element": match.group(1),
                    "text_width": int(match.group(2)),
                    "container": match.group(3),
                    "container_width": int(match.group(4)),
                    "overflow_px": int(match.group(2)) - int(match.group(4)),
                    "raw_message": failure,
                })

        # Parse overlap issues
        if "intersects" in failure:
            issues.append({
                "type": "overlap",
                "raw_message": failure,
            })

        # Parse visibility issues
        if "should be visible" in failure or "should be hidden" in failure:
            issues.append({
                "type": "visibility",
                "raw_message": failure,
            })

    return issues


def generate_fix_suggestions(issues: List[Dict[str, Any]]) -> List[str]:
    """Generate actionable fix suggestions for detected issues.

    Args:
        issues: Output from analyze_layout_issues()

    Returns:
        List of fix suggestions
    """
    suggestions = []

    for issue in issues:
        if issue["type"] == "overflow":
            element = issue["element"]
            overflow = issue["overflow_px"]
            suggestions.append(
                f"OVERFLOW: {element} text overflows by {overflow}px. "
                f"Increase widget width by at least {overflow + 10}px or shorten the label text."
            )

        elif issue["type"] == "overlap":
            suggestions.append(
                f"OVERLAP: Widgets are overlapping. Check layout constraints and margins."
            )

        elif issue["type"] == "visibility":
            suggestions.append(
                f"VISIBILITY: Widget visibility state incorrect. Check _update_state() logic."
            )

    return suggestions


def main():
    """Main entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(description="AI Visual Testing Helper")
    parser.add_argument("--output-dir", type=Path, help="Directory for screenshots")
    parser.add_argument("--analyze", action="store_true", help="Analyze and report issues")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    print("=" * 70)
    print("GUI Visual Testing - AI Agent Helper")
    print("=" * 70)

    # Run tests
    print("\n[1/3] Running visual tests...")
    results = run_visual_tests(args.output_dir, verbose=not args.json)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f"\n[2/3] Test Results: {results['passed']} passed, {results['failed']} failed")

    if args.analyze and results["failed"] > 0:
        print("\n[3/3] Analyzing layout issues...")
        issues = analyze_layout_issues(results)
        suggestions = generate_fix_suggestions(issues)

        if issues:
            print(f"\nDetected {len(issues)} layout issues:\n")
            for i, issue in enumerate(issues, 1):
                print(f"{i}. [{issue['type'].upper()}] {issue.get('raw_message', 'See details')}")

            print("\nSuggested fixes:\n")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion}")
        else:
            print("\nNo specific layout issues detected (check test output for details)")

    print("\n" + "=" * 70)
    if results["failed"] == 0:
        print("[OK] All visual tests passed!")
    else:
        print(f"[FAIL] {results['failed']} test(s) failed - review output above")
    print("=" * 70)

    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
