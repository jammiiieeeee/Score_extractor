# Learning Record: GitHub CI/CD Basics

## Date
2026-07-23

## What I Learned

1. **CI/CD workflow structure**: A GitHub Actions workflow has triggers (when), runners (where), and steps (what).

2. **Matrix strategy**: Can run the same job with different configurations (e.g., Python 3.10 + 3.12) in parallel.

3. **Caching**: Using `actions/cache@v4` to avoid re-downloading dependencies on every run.

4. **Test markers**: Using pytest markers (`-m "not slow"`) to run different test subsets in CI vs locally.

5. **Artifacts**: Files saved after a workflow run that can be downloaded from the GitHub UI.

## Key Insight

CI catches "works on my machine" bugs by running tests on a clean machine every time. For our project, this means:
- Tests run on a fresh Windows VM
- Dependencies installed from scratch
- No local state leaking into test results

## Next Steps

- Push `.github/workflows/test.yml` (needs PAT with `workflow` scope)
- Monitor first CI run on GitHub Actions tab
- Consider adding linting step (ruff/mypy) in future

## Questions to Explore

- How to add deployment steps?
- How to use secrets in workflows?
- How to set up branch protection rules?
