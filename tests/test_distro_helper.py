import unittest
from unittest.mock import MagicMock, patch

from sru_lint.common.distro_helper import get_esm_only_releases


class TestGetEsmOnlyReleases(unittest.TestCase):
    def _make_info(self, supported, esm):
        info = MagicMock()
        info.supported.return_value = supported
        info.supported_esm.return_value = esm
        return info

    @patch("sru_lint.common.distro_helper.UbuntuDistroInfo")
    def test_returns_esm_only(self, mock_cls):
        mock_cls.return_value = self._make_info(
            supported=["jammy", "noble"],
            esm=["bionic", "focal", "jammy", "noble"],
        )
        self.assertEqual(get_esm_only_releases(), ["bionic", "focal"])

    @patch("sru_lint.common.distro_helper.UbuntuDistroInfo")
    def test_no_esm_only(self, mock_cls):
        mock_cls.return_value = self._make_info(
            supported=["jammy", "noble"],
            esm=["jammy", "noble"],
        )
        self.assertEqual(get_esm_only_releases(), [])

    @patch("sru_lint.common.distro_helper.UbuntuDistroInfo")
    def test_result_is_sorted(self, mock_cls):
        mock_cls.return_value = self._make_info(
            supported=["noble"],
            esm=["bionic", "focal", "noble", "xenial"],
        )
        result = get_esm_only_releases()
        self.assertEqual(result, sorted(result))
