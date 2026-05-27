import fs from 'node:fs/promises';
import path from 'node:path';

const repoRoot = process.cwd();
const summaryPath = path.join(repoRoot, 'web', 'coverage', 'unit', 'coverage-summary.json');
const baselinePath = path.join(repoRoot, 'web', 'coverage-baseline.json');

function formatPct(value) {
  return Number(value).toFixed(2);
}

async function main() {
  const [summaryRaw, baselineRaw] = await Promise.all([
    fs.readFile(summaryPath, 'utf8'),
    fs.readFile(baselinePath, 'utf8'),
  ]);

  const summary = JSON.parse(summaryRaw);
  const baseline = JSON.parse(baselineRaw).frontendCoverageBaseline;

  const currentBranches = Number(summary.total.branches.pct);
  const currentFunctions = Number(summary.total.functions.pct);

  const requiredBranches = Number(baseline.branchesPct);
  const requiredFunctions = Number(baseline.functionsPct);

  const failures = [];
  if (currentBranches < requiredBranches) {
    failures.push(
      `Branches coverage regression: current ${formatPct(currentBranches)} < baseline ${formatPct(requiredBranches)}`
    );
  }
  if (currentFunctions < requiredFunctions) {
    failures.push(
      `Functions coverage regression: current ${formatPct(currentFunctions)} < baseline ${formatPct(requiredFunctions)}`
    );
  }

  if (failures.length > 0) {
    console.error('Frontend coverage regression detected.');
    failures.forEach((item) => console.error(`- ${item}`));
    process.exit(1);
  }

  console.log('Frontend coverage regression check passed.');
  console.log(`- Branches: ${formatPct(currentBranches)} (baseline ${formatPct(requiredBranches)})`);
  console.log(`- Functions: ${formatPct(currentFunctions)} (baseline ${formatPct(requiredFunctions)})`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
