import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/doctor-wechat-publisher/scripts/render_package.py'
spec = importlib.util.spec_from_file_location('renderer', SCRIPT)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.article = json.loads((ROOT / 'examples/nosebleed/article.json').read_text())

    def run_cli(self, article, folder, *options):
        source = folder / 'input.json'
        source.write_text(json.dumps(article))
        return subprocess.run([sys.executable, str(SCRIPT), str(source), '--out', str(folder / 'result'), *options], capture_output=True, text=True)

    def test_fresh_render_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.assertEqual(self.run_cli(self.article, folder).returncode, 0)
            output = folder / 'result/article.md'
            output.write_text('用户已经改过的稿件')
            self.assertEqual(self.run_cli(self.article, folder).returncode, 2)
            self.assertEqual(output.read_text(), '用户已经改过的稿件')
            self.assertEqual(self.run_cli(self.article, folder, '--overwrite').returncode, 0)
            self.assertIn(self.article['title'], output.read_text())

    def test_invalid_reference_produces_no_output(self):
        self.article['sections'][0]['paragraphs'][0]['source_ids'] = ['unknown']
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.assertEqual(self.run_cli(self.article, folder).returncode, 2)
            self.assertFalse((folder / 'result').exists())

    def test_markup_is_literal(self):
        text = '<script>alert(1)</script> [点我](javascript:alert(1))'
        self.article['sections'][0]['paragraphs'][0]['text'] = text
        md, page = renderer.render(renderer.validate(self.article))
        self.assertNotIn('<script>', page)
        self.assertNotIn('<script>', md)
        self.assertIn('\\[点我\\]', md)
        self.assertIn('&lt;script&gt;', page)

    def test_reject_invalid_inputs(self):
        changes = [
            lambda d: d['sources'][0].update(url='javascript:alert(1)'),
            lambda d: d['sources'].append(copy.deepcopy(d['sources'][0])),
            lambda d: d['brand'].update(color='red;display:none'),
            lambda d: d.update(updated='2026-02-30'),
            lambda d: d.update(status='clinician_reviewed'),
        ]
        for change in changes:
            data = copy.deepcopy(self.article)
            change(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                renderer.validate(data)

    def test_review_record_is_visible(self):
        self.article.update(status='clinician_reviewed', review={'reviewer': '测试审核者', 'date': '2026-09-17', 'version': 'test-only'})
        md, page = renderer.render(renderer.validate(self.article))
        self.assertIn('测试审核者', md)
        self.assertIn('test-only', page)

    def test_reproducible_output(self):
        a = renderer.render(renderer.validate(self.article))
        self.assertEqual(a, renderer.render(renderer.validate(copy.deepcopy(self.article))))
        for source in self.article['sources']:
            self.assertIn(source['url'], a[1])

    def test_skill_can_be_copied_to_clean_directory(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'skills/doctor-wechat-publisher'
            shutil.copytree(ROOT / 'skills/doctor-wechat-publisher', dest, ignore=shutil.ignore_patterns('__pycache__'))
            self.assertTrue((dest / 'SKILL.md').is_file())
            source = Path(temp) / 'input.json'
            source.write_text(json.dumps(self.article))
            result = subprocess.run([sys.executable, str(dest / 'scripts/render_package.py'), str(source), '--out', str(Path(temp) / 'result')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
