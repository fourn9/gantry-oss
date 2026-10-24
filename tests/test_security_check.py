import unittest
from gantry.security_check import assess


class SecurityCheckTests(unittest.TestCase):
    def test_python_patch_boundaries(self):
        for good, bad in [('3.11.17', '3.11.16'), ('3.12.15', '3.12.14'),
                          ('3.13.17', '3.13.16'), ('3.14.9', '3.14.8'),
                          ('3.15.1', '3.15.0')]:
            with self.subTest(good=good):
                self.assertFalse(assess(good, {})['findings'])
                self.assertTrue(assess(bad, {})['findings'])

    def test_prerelease_unsupported_and_non_cpython_need_review(self):
        for version in ['3.14.9rc1', '3.10.22', '3.16.0', 'unknown']:
            self.assertTrue(assess(version, {})['findings'])
        self.assertTrue(assess('3.12.15', {}, implementation='PyPy')['findings'])

    def test_installed_tooling_is_checked_but_missing_is_not_installed(self):
        old = {'pip': '26.2.1', 'certifi': '2026.10.18', 'uv': '0.13.3',
               'PyNaCl': '1.6.1', 'setuptools': '78.1.0'}
        result = assess('3.12.15', old)
        self.assertEqual({f['component'] for f in result['findings']}, set(old))
        good = {'pip': '26.2.2', 'certifi': '2026.10.19', 'uv': '0.13.4',
                'PyNaCl': '1.6.2', 'setuptools': '78.1.1'}
        self.assertFalse(assess('3.12.15', good)['findings'])
        self.assertFalse(assess('3.12.15', {})['findings'])
        self.assertIn('OS trust store', ' '.join(result['limitations']))

    def test_unparseable_package_version_is_not_reported_as_patched(self):
        self.assertTrue(assess('3.12.15', {'pip': '26.2.2rc1'})['findings'])
