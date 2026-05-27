# Feature Test Checklist

Use this checklist for every new feature branch before merge.

## 1. Feature Contract
- [ ] Feature behavior is described in a short requirement statement.
- [ ] Success criteria are measurable (UI state, API response, side effect).
- [ ] Failure behavior is defined (errors, fallbacks, retries).

## 2. Backend Coverage
- [ ] Add or update pytest tests in src/tests.
- [ ] Include feature metadata via test docstring or marker.
- [ ] Validate both happy path and at least one non-happy branch.
- [ ] Keep backend total coverage at or above 80.

## 3. Frontend Coverage
- [ ] Add or update component/app tests in web/src/test.
- [ ] Use Feature naming in test titles.
- [ ] Cover one interaction path and one error/fallback path.
- [ ] Ensure frontend branches/functions do not regress versus baseline.

## 4. End-to-End Coverage
- [ ] Add or update Playwright scenario when user journey changes.
- [ ] Verify selectors are role/label based and stable.
- [ ] Verify flow passes in local run and CI.

## 5. Documentation and Traceability
- [ ] Run the test-index sync script to refresh the auto-generated section in docs/TEST_REQUIREMENTS_DESIGN.md.
- [ ] Confirm new tests are reflected in the generated test index.
- [ ] Include testing notes in PR summary.

## 6. Release Safety
- [ ] Lint/build pass for affected packages.
- [ ] All relevant tests pass.
- [ ] No generated artifacts or crash dumps are committed.
