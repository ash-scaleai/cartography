"""
Tests for driftdetect package_info metadata.
"""

from cartography.driftdetect import package_info


class TestDriftdetectPackageInfo:

    def test_package_name(self):
        assert package_info.PACKAGE_NAME == "cartography-driftdetect"

    def test_version_is_valid(self):
        parts = package_info.VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_description_nonempty(self):
        assert len(package_info.DESCRIPTION) > 10

    def test_core_dependency_listed(self):
        assert package_info.CORE_DEPENDENCY.startswith("cartography-core")

    def test_install_requires_includes_core(self):
        assert package_info.CORE_DEPENDENCY in package_info.INSTALL_REQUIRES

    def test_third_party_deps_are_listed(self):
        dep_names = [d.split(">=")[0].split("<")[0] for d in package_info.THIRD_PARTY_DEPENDENCIES]
        assert "neo4j" in dep_names
        assert "marshmallow" in dep_names

    def test_core_imports_documented(self):
        assert len(package_info.CARTOGRAPHY_CORE_IMPORTS) > 0
        for imp in package_info.CARTOGRAPHY_CORE_IMPORTS:
            assert imp.startswith("cartography.")

    def test_entry_points(self):
        scripts = package_info.ENTRY_POINTS["console_scripts"]
        assert any("cartography-detectdrift" in s for s in scripts)
