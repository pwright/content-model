"""
Re-extract upstream inventory with proper section-level grain.

For non-refdog .md files with multiple anchored+annotated sections,
splits them into one entry per section. Preserves refdog entries as-is.
"""
import re
import os
import yaml

INPUT_DIR = "skupper-docs/input"
INVENTORY_PATH = "content-model/upstream-inventory.yaml"

CONTENT_TYPE_PATTERN = re.compile(r'<!--\s*(ASSEMBLY|CONCEPT|PROCEDURE|TASK|REFERENCE)\s*-->')
ANCHOR_PATTERN = re.compile(r'<a\s+id="([^"]+)"')
HEADING_PATTERN = re.compile(r'^(#{1,4})\s+(.+)$')

def extract_sections(filepath, relpath):
    """Extract anchored sections from a markdown file."""
    with open(filepath, 'r') as f:
        lines = f.readlines()

    sections = []
    current_anchor = None
    current_title = None
    current_type = None
    pending_anchor = None

    for line in lines:
        line_stripped = line.strip()

        anchor_match = ANCHOR_PATTERN.search(line_stripped)
        if anchor_match:
            pending_anchor = anchor_match.group(1)
            continue

        heading_match = HEADING_PATTERN.match(line_stripped)
        if heading_match:
            title_text = heading_match.group(2).strip()
            # Clean up template variables for readability
            title_text = title_text.replace('{{skupper_name}}', 'Skupper')
            title_text = title_text.replace('{{skupper_product_name}}', 'Red Hat Service Interconnect')

            if current_anchor is not None and current_title is not None:
                sections.append({
                    'anchor': current_anchor,
                    'title': current_title,
                    'content_type': current_type,
                })

            current_anchor = pending_anchor
            current_title = title_text
            current_type = None
            pending_anchor = None
            continue

        type_match = CONTENT_TYPE_PATTERN.search(line_stripped)
        if type_match:
            current_type = type_match.group(1)
            continue

    # Don't forget the last section
    if current_anchor is not None and current_title is not None:
        sections.append({
            'anchor': current_anchor,
            'title': current_title,
            'content_type': current_type,
        })

    return sections


def extract_file_title(filepath):
    """Get the title from frontmatter navtitle or first heading."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Check frontmatter
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            frontmatter = content[3:end]
            for line in frontmatter.split('\n'):
                if line.strip().startswith('navtitle:'):
                    return line.split(':', 1)[1].strip()

    # Fall back to first heading
    for line in content.split('\n'):
        m = HEADING_PATTERN.match(line.strip())
        if m:
            title = m.group(2).strip()
            title = title.replace('{{skupper_name}}', 'Skupper')
            title = title.replace('{{skupper_product_name}}', 'Red Hat Service Interconnect')
            return title

    return os.path.basename(filepath)


def build_inventory():
    topics = []

    # Walk non-refdog directories
    for root, dirs, files in os.walk(INPUT_DIR):
        relroot = os.path.relpath(root, INPUT_DIR)
        if relroot.startswith('refdog'):
            continue

        for fname in sorted(files):
            if not fname.endswith('.md'):
                continue

            filepath = os.path.join(root, fname)
            if relroot == '.':
                relpath = fname
            else:
                relpath = os.path.join(relroot, fname)

            sections = extract_sections(filepath, relpath)

            if len(sections) > 1:
                # Multi-section file: emit one entry per section
                for sec in sections:
                    entry = {
                        'path': relpath,
                        'anchor': sec['anchor'],
                        'title': sec['title'],
                        'source_category': 'guide',
                    }
                    if sec['content_type']:
                        entry['content_type'] = sec['content_type']
                    topics.append(entry)
            elif len(sections) == 1:
                # Single section with anchor
                sec = sections[0]
                entry = {
                    'path': relpath,
                    'title': sec['title'],
                    'source_category': 'guide',
                }
                if sec['anchor']:
                    entry['anchor'] = sec['anchor']
                if sec['content_type']:
                    entry['content_type'] = sec['content_type']
                topics.append(entry)
            else:
                # No anchored sections, file-level entry
                title = extract_file_title(filepath)
                entry = {
                    'path': relpath,
                    'title': title,
                    'source_category': 'guide',
                }
                topics.append(entry)

    # Now load existing refdog entries and append them unchanged
    with open(INVENTORY_PATH, 'r') as f:
        existing = yaml.safe_load(f)

    for topic in existing.get('upstream_topics', []):
        if topic.get('path', '').startswith('refdog'):
            topics.append(topic)

    return topics


def main():
    topics = build_inventory()

    guide_count = sum(1 for t in topics if t.get('source_category') == 'guide')
    ref_count = sum(1 for t in topics if t.get('source_category') == 'reference')
    anchored = sum(1 for t in topics if 'anchor' in t)

    print(f"Total upstream topics: {len(topics)}")
    print(f"  Guide: {guide_count}")
    print(f"  Reference (refdog): {ref_count}")
    print(f"  With anchors (section-level): {anchored}")

    # Count by content_type
    by_type = {}
    for t in topics:
        ct = t.get('content_type', 'unannotated')
        by_type[ct] = by_type.get(ct, 0) + 1
    print(f"  By content_type: {by_type}")

    # Show multi-section files
    from collections import Counter
    path_counts = Counter(t['path'] for t in topics if t.get('source_category') == 'guide')
    multi = {p: c for p, c in path_counts.items() if c > 1}
    if multi:
        print(f"\nMulti-section files ({len(multi)}):")
        for p, c in sorted(multi.items()):
            print(f"  {p}: {c} sections")

    output = {'upstream_topics': topics}
    with open(INVENTORY_PATH, 'w') as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)

    print(f"\nWrote {len(topics)} topics to {INVENTORY_PATH}")


if __name__ == '__main__':
    main()
