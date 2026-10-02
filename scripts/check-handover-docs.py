"""Read-only check of local links/anchors in current handover entry points."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FILES = ["README.md", "ROADMAP.md", "CHANGELOG.md", "AGENTS.md", "CLAUDE.md", *[
    "docs/" + name + ".md" for name in ("USER_GUIDE", "DEPLOYMENT_GUIDE", "WECHAT_SETUP", "OPERATIONS_RUNBOOK",
    "ARCHITECTURE", "REQUIREMENTS_TRACEABILITY", "BUILD_ARTIFACT_GUIDE", "HANDOVER_CHANGE_CHECKLIST",
    "HANDOVER_DOCUMENTATION_REPORT", "PROJECT_FILE_GUIDE", "MAIN_INTEGRATION_REPORT",
    "HANDOVER_GUIDE", "HANDOVER_PACKAGE_REPORT", "RELEASE_CHECKLIST", "PILOT_RELEASE_BASELINE", "GITHUB_ADMIN_SETUP")]]


def anchors(text):
    result = set()
    seen = {}
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.M):
        slug = re.sub(r"[^\w\-\s]", "", heading.lower()).strip().replace(" ", "-")
        number = seen.get(slug, 0)
        seen[slug] = number + 1
        result.add(slug + (f"-{number}" if number else ""))
    return result


errors = []
checked = 0
for name in FILES:
    source = ROOT / name
    text = source.read_text()
    for destination in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        destination = destination.strip().strip("<>")
        link = urlsplit(destination)
        if link.scheme or link.netloc:
            continue
        target = source.parent / unquote(link.path) if link.path else source
        checked += 1
        if not target.exists():
            errors.append(f"{name}: missing {destination}")
        elif link.fragment and target.is_file() and target.suffix == ".md" and unquote(link.fragment) not in anchors(target.read_text()):
            errors.append(f"{name}: missing anchor {destination}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
print(f"交付文档链接通过: {len(FILES)}个当前文档，{checked}个本地链接/锚点")
