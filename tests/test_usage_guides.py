import unittest
import usage_guides


class GuideTest(unittest.TestCase):
    def item(self):
        guide = usage_guides.CATALOG['Trace32_CLI']
        return dict(name='Trace32_CLI', pages=[], description='Original README', documentHashes=dict(guide['evidence']))

    def test_reviewed_guide_requires_exact_source_revision(self):
        item = self.item()
        usage_guides.attach(item)
        self.assertEqual(item['usageGuide']['status'], 'reviewed')
        self.assertNotEqual(item['description'], 'Original README')
        item['documentHashes']['new/SKILL.md'] = 'changed'
        usage_guides.attach(item)
        self.assertEqual(item['usageGuide']['status'], 'stale')
        self.assertNotIn('steps', item['usageGuide'])

    def test_unknown_project_has_no_invented_steps(self):
        item = dict(name='unknown', pages=[])
        usage_guides.attach(item)
        self.assertEqual(item['usageGuide']['status'], 'missing')
        self.assertNotIn('steps', item['usageGuide'])

    def test_catalog_has_actionable_guides_and_placeholder_limits(self):
        self.assertEqual(len(usage_guides.CATALOG), 29)
        for guide in usage_guides.CATALOG.values():
            for key in ['purpose', 'when', 'inputs', 'outputs', 'example', 'limits', 'evidence']:
                self.assertTrue(guide[key])
            self.assertGreaterEqual(len(guide['steps']), 3)
        self.assertIn('尚未提供', usage_guides.CATALOG['sport-record-parser']['purpose'])
        self.assertIn('占位', usage_guides.CATALOG['code-review']['purpose'])
