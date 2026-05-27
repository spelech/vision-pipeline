import fs from 'node:fs/promises';
import path from 'node:path';

const repoRoot = process.cwd();
const docPath = path.join(repoRoot, 'docs', 'TEST_REQUIREMENTS_DESIGN.md');

const startMarker = '<!-- AUTO-GENERATED-TEST-INDEX:START -->';
const endMarker = '<!-- AUTO-GENERATED-TEST-INDEX:END -->';

async function listFilesRecursive(dirPath, predicate) {
  const result = [];
  const entries = await fs.readdir(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      const nested = await listFilesRecursive(full, predicate);
      result.push(...nested);
    } else if (predicate(full)) {
      result.push(full);
    }
  }
  return result;
}

function rel(filePath) {
  return path.relative(repoRoot, filePath).replace(/\\/g, '/');
}

function extractMatches(content, regex) {
  const values = [];
  let match;
  while ((match = regex.exec(content)) !== null) {
    values.push(match[1].trim());
  }
  return values;
}

async function collectFrontendFeatureTests() {
  const testDir = path.join(repoRoot, 'web', 'src', 'test');
  const files = await listFilesRecursive(testDir, (p) => /\.(test|spec)\.[jt]sx?$/.test(p));
  const index = [];
  for (const filePath of files) {
    const content = await fs.readFile(filePath, 'utf8');
    const features = extractMatches(content, /Feature:\s*([^'"\n]+)/g);
    if (features.length > 0) {
      index.push({ file: rel(filePath), tests: features });
    }
  }
  return index;
}

async function collectBackendFeatureTests() {
  const testDir = path.join(repoRoot, 'src', 'tests');
  const files = await listFilesRecursive(testDir, (p) => /^test_.*\.py$/.test(path.basename(p)));
  const index = [];
  for (const filePath of files) {
    const content = await fs.readFile(filePath, 'utf8');
    const features = extractMatches(content, /Feature:\s*([^"'\n]+)/g);
    const testNames = extractMatches(content, /def\s+(test_[a-zA-Z0-9_]+)\s*\(/g);
    if (features.length > 0 || testNames.length > 0) {
      index.push({ file: rel(filePath), features, testNames });
    }
  }
  return index;
}

async function collectE2eTests() {
  const roots = [path.join(repoRoot, 'e2e'), path.join(repoRoot, 'web', 'e2e')];
  const index = [];
  for (const root of roots) {
    let files = [];
    try {
      files = await listFilesRecursive(root, (p) => /\.spec\.[jt]s$/.test(p));
    } catch {
      files = [];
    }

    for (const filePath of files) {
      const content = await fs.readFile(filePath, 'utf8');
      const tests = extractMatches(content, /test\(\s*['"`]([^'"`]+)['"`]/g);
      if (tests.length > 0) {
        index.push({ file: rel(filePath), tests });
      }
    }
  }
  return index;
}

function renderSection(frontend, backend, e2e) {
  const lines = [];

  lines.push('## 9. Auto-Generated Test Index');
  lines.push('Updated by script: scripts/update-test-requirements-index.mjs');
  lines.push('');

  lines.push('### 9.1 Frontend Feature Tests');
  if (frontend.length === 0) {
    lines.push('- No frontend feature tests discovered.');
  } else {
    for (const group of frontend) {
      lines.push(`- ${group.file}`);
      for (const test of group.tests) {
        lines.push(`  - ${test}`);
      }
    }
  }
  lines.push('');

  lines.push('### 9.2 Backend Feature Tests');
  if (backend.length === 0) {
    lines.push('- No backend feature tests discovered.');
  } else {
    for (const group of backend) {
      lines.push(`- ${group.file}`);
      if (group.features.length > 0) {
        lines.push('  - Feature labels:');
        for (const feature of group.features) {
          lines.push(`    - ${feature}`);
        }
      }
      if (group.testNames.length > 0) {
        lines.push('  - Test functions:');
        for (const testName of group.testNames) {
          lines.push(`    - ${testName}`);
        }
      }
    }
  }
  lines.push('');

  lines.push('### 9.3 End-to-End Scenarios');
  if (e2e.length === 0) {
    lines.push('- No e2e tests discovered.');
  } else {
    for (const group of e2e) {
      lines.push(`- ${group.file}`);
      for (const scenario of group.tests) {
        lines.push(`  - ${scenario}`);
      }
    }
  }

  return lines.join('\n');
}

function updateDocument(doc, generatedSection) {
  const wrapped = `${startMarker}\n${generatedSection}\n${endMarker}`;

  if (doc.includes(startMarker) && doc.includes(endMarker)) {
    const start = doc.indexOf(startMarker);
    const end = doc.indexOf(endMarker) + endMarker.length;
    return `${doc.slice(0, start)}${wrapped}${doc.slice(end)}`;
  }

  const trimmed = doc.trimEnd();
  return `${trimmed}\n\n${wrapped}\n`;
}

async function main() {
  const checkMode = process.argv.includes('--check');

  const [frontend, backend, e2e, doc] = await Promise.all([
    collectFrontendFeatureTests(),
    collectBackendFeatureTests(),
    collectE2eTests(),
    fs.readFile(docPath, 'utf8'),
  ]);

  const generatedSection = renderSection(frontend, backend, e2e);
  const updatedDoc = updateDocument(doc, generatedSection);

  if (checkMode) {
    if (updatedDoc !== doc) {
      console.error('docs/TEST_REQUIREMENTS_DESIGN.md is out of date.');
      console.error('Run: node scripts/update-test-requirements-index.mjs');
      process.exit(1);
    }
    console.log('Test requirements document index is up to date.');
    return;
  }

  await fs.writeFile(docPath, updatedDoc, 'utf8');
  console.log('Updated docs/TEST_REQUIREMENTS_DESIGN.md auto-generated test index section.');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
