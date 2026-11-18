"""Reviewed plain-language guides, tied to exact source document revisions."""
import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).parent / 'static/usage_guides.json').read_text(encoding='utf-8'))


def attach(item):
    if item['pages']:
        return
    guide = CATALOG.get(item['name'])
    if not guide:
        item['usageGuide'] = dict(status='missing', message='这个项目还没有经过整理的使用指南。请从项目文件核对真实用途与入口，暂不提供推测的使用步骤。')
        return
    if guide['evidence'] != item.get('documentHashes'):
        item['usageGuide'] = dict(status='stale', message='项目说明已变化，原指南需要重新核对。请查看当前来源文件，暂不展示旧步骤。')
        return
    item['usageGuide'] = dict(guide, status='reviewed', message='已按当前项目说明整理；未在本机执行业务验证。')
    item['description'] = guide['purpose']
