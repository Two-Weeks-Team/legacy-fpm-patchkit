import { parseArgs } from 'node:util';
import { FileStore } from './file-store.ts';
import { runBatch } from './batch.ts';
import { readView, payload, backlogMarkdown, KINDS } from './export.ts';
import type { Kind } from './export.ts';
import seed from './seed.ts';
try {
  const { values, positionals } = parseArgs({ allowPositionals: true, options: {
    'state-dir': { type: 'string', default: '.work/advisory-sync' },
    kind: { type: 'string', default: 'backlog' }, format: { type: 'string', default: 'json' }, help: { type: 'boolean' },
  }});
  if (values.help) console.log('batch [sync|export] [--state-dir DIR] [--kind status|catalog|coverage|changes|backlog] [--format json|markdown]');
  else {
    if (positionals.length > 1 || !['sync','export'].includes(positionals[0] ?? 'sync')) throw new Error('Unknown batch command');
    if (!KINDS.includes(values.kind as Kind) || !['json','markdown'].includes(values.format)) throw new Error('Unknown export kind or format');
    const store = new FileStore(values['state-dir']);
    if ((positionals[0] ?? 'sync') === 'sync') {
      const result = await runBatch(store, seed, { trigger: 'cli' }); console.log(JSON.stringify(result, null, 2));
      process.exitCode = result.status === 'SUCCESS' ? 0 : result.status === 'BUSY' ? 2 : 1;
    } else {
      const view = await readView(store);
      if (values.format === 'markdown') {
        if (values.kind !== 'backlog') throw new Error('Markdown format is available for backlog only');
        process.stdout.write(backlogMarkdown(view));
      } else console.log(JSON.stringify(payload(view, values.kind as Kind), null, 2));
    }
  }
} catch (error) { console.error(JSON.stringify({ error: error instanceof Error ? error.message : 'Batch failed' })); process.exitCode = 1; }
