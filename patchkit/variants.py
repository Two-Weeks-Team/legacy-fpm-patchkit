"""Named repository-pinned source variants. No caller-controlled trust roots."""
import json
import os
from pathlib import Path
import shutil

from . import sources

DEFAULT = 'build007'
# Fixed repository-relative manifest/patch names; values pin the manifest bytes.
PINNED_VARIANTS = {'acl-filter-20261114': 'e75f242ee002c1aebe29cf031541d2c80a69ecead94252780491f6c814d11f44',
                   'multipart-20261114': 'ceb74f54416dd9d4ffe3f668e5c1b7651565d7d7ac0bf69e6d17640a8e1ad2f4',
                   'cookie-20261114': '73fe27ba703a6770b5e3959e4c76ef72580609eb809ed02743aa9c2c9f0e7629',
                   'fpm-log-20261114': '5c92b7ac32f3bb93255d65997969923d3a3a29112185c9faf1e427a88a003651'}


def manifest(variant):
    if variant not in PINNED_VARIANTS:
        raise ValueError('unknown source variant: ' + variant)
    path = sources.ROOT / 'provenance/variants' / (variant + '.json')
    sources.verify_file(path, PINNED_VARIANTS[variant])
    result = json.loads(path.read_text())
    if result['schema'] != 1 or result['variant'] != variant :
        raise ValueError('invalid source variant identity')
    base_name = result['base_variant']
    if base_name == DEFAULT:
        base = json.loads((sources.ROOT / 'provenance/inputs.json').read_text())
        old = json.loads((sources.ROOT / 'provenance/build007-source.json').read_text())
        base_source, base_patch = base['normalized_candidate_sha256'], old['patch_sha256']
    elif (variant, base_name) in (('multipart-20261114', 'acl-filter-20261114'), ('cookie-20261114', 'multipart-20261114'), ('fpm-log-20261114', 'cookie-20261114')):
        parent = manifest(base_name)
        base_source, base_patch = parent['candidate_source_sha256'], parent['patch_sha256']
    else:
        raise ValueError('invalid fixed parent variant')
    if result['baseline_source_sha256'] != base_source or result['baseline_patch_sha256'] != base_patch:
        raise ValueError('source variant baseline provenance mismatch')
    sources.verify_file(sources.ROOT / 'patches' / (base_name + '.patch'), base_patch)
    sources.verify_file(sources.ROOT / 'patches' / (variant + '.patch'), result['patch_sha256'])
    for name in result['changed']:
        sources.relative(name)
    return result


def verify_source(source, variant=DEFAULT):
    if variant == DEFAULT:
        pin = json.loads((sources.ROOT / 'provenance/inputs.json').read_text())
        old = json.loads((sources.ROOT / 'provenance/build007-source.json').read_text())
        sources.verify_file(sources.ROOT / 'patches/build007.patch', old['patch_sha256'])
        expected = pin['normalized_candidate_sha256']
        identity = {'variant': DEFAULT, 'patch_sha256': old['patch_sha256']}
    else:
        fixed = manifest(variant)
        sources.verify_changed(source, fixed, 'after')
        expected = fixed['candidate_source_sha256']
        identity = {'variant': variant, 'patch_sha256': fixed['patch_sha256'],
                    'baseline_variant': fixed['base_variant'],
                    'baseline_source_sha256': fixed['baseline_source_sha256'],
                    'baseline_patch_sha256': fixed['baseline_patch_sha256'],
                    'variant_manifest_sha256': PINNED_VARIANTS[variant],
                    'changed': fixed['changed']}
    actual = sources.tree_digest(source, normalized=True)
    if actual != expected:
        raise ValueError('normalized source tree mismatch: ' + actual)
    identity['normalized_source_sha256'] = actual
    identity['result'] = 'SOURCE_VERIFIED'
    return identity


def prepare_from_baseline(baseline, destination, variant):
    """New full tree from its fixed verified parent; input remains unchanged."""
    destination = Path(destination)
    sources.new_outputs(destination)
    fixed = manifest(variant)
    verify_source(baseline, fixed['base_variant'])
    sources.verify_changed(baseline, fixed, 'before')
    with sources.preparation_workspace(destination) as stage:
        prepared = stage / 'source'
        shutil.copytree(baseline, prepared)
        # Detect drift during the copy, including unrelated source files.
        verify_source(prepared, fixed['base_variant'])
        log = stage / 'preparation.log'
        sources.run_patch(prepared, sources.ROOT / 'patches' / (variant + '.patch'), log)
        receipt = verify_source(prepared, variant)
        receipt.update(schema=1, binary_compatibility='NOT_TESTED')
        record = stage / 'receipt.json'
        record.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        # mkdir is exclusive even if another owner races the initial preflight.
        # Partial publication stays visibly incomplete on failure; never erase it.
        destination.mkdir()
        for child in prepared.iterdir():
            child.rename(destination / child.name)
        os.link(log, Path(str(destination) + '.preparation.log'))
        os.link(record, Path(str(destination) + '.preparation.json'))
    return receipt


def prepare(cache, destination, variant):
    """Keep the original build007 transaction intact; layer an explicit delta."""
    sources.new_outputs(destination)
    fixed = manifest(variant)  # Verify the whole fixed chain before any work.
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.TemporaryDirectory(prefix='.variant-base-', dir=destination.parent) as work:
        baseline = Path(work) / fixed['base_variant']
        if fixed['base_variant'] == DEFAULT:
            sources.prepare(cache, baseline)
        else:
            prepare(cache, baseline, fixed['base_variant'])
        return prepare_from_baseline(baseline, destination, variant)
