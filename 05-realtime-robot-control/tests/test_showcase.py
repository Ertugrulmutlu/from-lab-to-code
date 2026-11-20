import tempfile
import unittest
from pathlib import Path
from tools.update_showcase import integrate, update_card, update_readme


class ShowcaseTests(unittest.TestCase):
    def test_script_replaces_only_expected_project(self):
        original = "const PROJECTS = [\n  {id:'05',title:'Control Basics',status:'planned'},\n  {id:'06',title:'Other'},\n];\n"
        updated = update_card(original)
        self.assertIn("'Real-Time Robot Control Lab'", updated)
        self.assertIn("{id:'06',title:'Other'}", updated)
        self.assertIn("articleUrl: ''", updated)
        self.assertEqual(updated, update_card(updated))

    def test_local_dry_run_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'docs').mkdir()
            (root/'05-realtime-robot-control').mkdir()
            js=root/'docs/app.js'
            readme=root/'README.md'
            original_js="const PROJECTS = [\n  {id:'05',title:'Control Basics',status:'planned'},\n];\n"
            original_readme='| # | Project | Topics |\n| --- | --- | --- |\n| 04 | Previous | Previous topic |\n'
            js.write_text(original_js,encoding='utf-8')
            readme.write_text(original_readme,encoding='utf-8')
            self.assertEqual(len(integrate(root,True)),2)
            self.assertEqual(js.read_text(),original_js)
            self.assertEqual(readme.read_text(),original_readme)
            self.assertEqual(len(integrate(root,False)),2)
            self.assertIn('Real-Time Robot Control Lab',js.read_text())
            self.assertIn('Real-Time Robot Control Lab',readme.read_text())
            self.assertEqual(integrate(root,False),['UNCHANGED docs/app.js','UNCHANGED README.md'])

    def test_missing_marker_prevents_changes(self):
        with self.assertRaises(ValueError):
            update_card("const PROJECTS = [];")
        with self.assertRaises(ValueError):
            update_readme('No project table here')


if __name__=='__main__': unittest.main()
