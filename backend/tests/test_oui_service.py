"""
Tests for OUIService
"""

import pytest
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.oui_service import OUIService


class TestOUIService:
    """Tests for OUI Service"""

    @pytest.fixture
    def oui_service(self):
        """Create OUI service instance"""
        return OUIService()

    def test_oui_service_loads_database(self, oui_service):
        """Test that OUI database is loaded"""
        assert oui_service.get_database_size() > 0, "OUI database should be loaded"

    def test_oui_service_database_size(self, oui_service):
        """Test that database has expected number of entries"""
        size = oui_service.get_database_size()
        assert size >= 100, f"Expected at least 100 OUI entries, got {size}"

    def test_oui_lookup_finds_apple(self, oui_service):
        """Test OUI lookup for Apple devices"""
        vendor = oui_service.lookup_vendor("001A2B:DD:EE:FF")
        assert vendor == "Apple Inc.", f"Expected 'Apple Inc.', got '{vendor}'"

    def test_oui_lookup_finds_tp_link(self, oui_service):
        """Test OUI lookup for TP-Link devices"""
        vendor = oui_service.lookup_vendor("0014BF:AA:BB:CC")
        assert vendor == "TP-Link", f"Expected 'TP-Link', got '{vendor}'"

    def test_oui_lookup_finds_cisco(self, oui_service):
        """Test OUI lookup for Cisco devices"""
        vendor = oui_service.lookup_vendor("001018:AA:BB:CC")
        assert vendor == "Cisco Systems Inc.", f"Expected 'Cisco Systems Inc.', got '{vendor}'"

    def test_oui_lookup_case_insensitive_uppercase(self, oui_service):
        """Test OUI lookup is case-insensitive with uppercase MAC"""
        vendor1 = oui_service.lookup_vendor("001A2B:DD:EE:FF")
        vendor2 = oui_service.lookup_vendor("001a2b:dd:ee:ff")
        assert vendor1 == vendor2, "Lookup should be case-insensitive"

    def test_oui_lookup_case_insensitive_lowercase(self, oui_service):
        """Test OUI lookup is case-insensitive with lowercase MAC"""
        vendor = oui_service.lookup_vendor("001a2b:dd:ee:ff")
        assert vendor == "Apple Inc."

    def test_oui_lookup_case_insensitive_mixed(self, oui_service):
        """Test OUI lookup is case-insensitive with mixed case MAC"""
        vendor = oui_service.lookup_vendor("001A2b:Dd:Ee:Ff")
        assert vendor == "Apple Inc."

    def test_oui_lookup_unknown_vendor(self, oui_service):
        """Test OUI lookup returns Unknown Vendor for unknown OUI"""
        vendor = oui_service.lookup_vendor("FFFFFF:FF:FF:FF")
        assert vendor == "Unknown Vendor", f"Expected 'Unknown Vendor', got '{vendor}'"

    def test_oui_lookup_with_hyphens(self, oui_service):
        """Test OUI lookup with hyphenated MAC address"""
        vendor = oui_service.lookup_vendor("001A-2B-DD-EE-FF")
        assert vendor == "Apple Inc."

    def test_oui_lookup_with_dots(self, oui_service):
        """Test OUI lookup with dotted MAC address"""
        vendor = oui_service.lookup_vendor("001A.2B.DD.EE.FF")
        assert vendor == "Apple Inc."

    def test_oui_lookup_caching(self, oui_service):
        """Test that OUI lookups are cached"""
        mac = "001A2B:DD:EE:FF"
        initial_cache_size = oui_service.get_cache_size()

        # Lookup vendor
        vendor1 = oui_service.lookup_vendor(mac)
        cache_size_after_first = oui_service.get_cache_size()

        # Lookup same vendor again
        vendor2 = oui_service.lookup_vendor(mac)
        cache_size_after_second = oui_service.get_cache_size()

        assert vendor1 == vendor2, "Same lookup should return same vendor"
        assert cache_size_after_first == cache_size_after_second, "Cache size should not increase on second lookup"
        assert cache_size_after_first > initial_cache_size, "Cache should have grown after first lookup"

    def test_oui_cache_size(self, oui_service):
        """Test cache size tracking"""
        initial_size = oui_service.get_cache_size()
        oui_service.lookup_vendor("001A2B:DD:EE:FF")
        new_size = oui_service.get_cache_size()
        assert new_size > initial_size

    def test_oui_clear_cache(self, oui_service):
        """Test cache clearing"""
        oui_service.lookup_vendor("001A2B:DD:EE:FF")
        assert oui_service.get_cache_size() > 0

        oui_service.clear_cache()
        assert oui_service.get_cache_size() == 0

    def test_oui_reload_database(self, oui_service):
        """Test database reload"""
        original_size = oui_service.get_database_size()
        oui_service.lookup_vendor("001A2B:DD:EE:FF")
        assert oui_service.get_cache_size() > 0

        oui_service.reload_database()

        # Database size should be same after reload
        assert oui_service.get_database_size() == original_size
        # Cache should be cleared
        assert oui_service.get_cache_size() == 0

    def test_oui_lookup_invalid_mac_short(self, oui_service):
        """Test OUI lookup with invalid short MAC"""
        vendor = oui_service.lookup_vendor("001A")
        assert vendor == "Unknown Vendor"

    def test_oui_lookup_invalid_mac_long(self, oui_service):
        """Test OUI lookup with invalid long MAC"""
        vendor = oui_service.lookup_vendor("001A2BDD:EE:FF:FF:FF")
        assert vendor == "Unknown Vendor"

    def test_oui_lookup_invalid_mac_non_hex(self, oui_service):
        """Test OUI lookup with non-hex MAC"""
        vendor = oui_service.lookup_vendor("ZZ:ZZ:ZZ:DD:EE:FF")
        assert vendor == "Unknown Vendor"

    def test_oui_lookup_empty_mac(self, oui_service):
        """Test OUI lookup with empty MAC"""
        vendor = oui_service.lookup_vendor("")
        assert vendor == "Unknown Vendor"

    def test_oui_lookup_none_mac(self, oui_service):
        """Test OUI lookup with None MAC"""
        vendor = oui_service.lookup_vendor(None)
        assert vendor == "Unknown Vendor"

    def test_oui_multiple_vendors(self, oui_service):
        """Test lookups for multiple vendors"""
        test_cases = [
            ("001A2B:DD:EE:FF", "Apple Inc."),
            ("0014BF:AA:BB:CC", "TP-Link"),
            ("001018:AA:BB:CC", "Cisco Systems Inc."),
        ]

        for mac, expected_vendor in test_cases:
            vendor = oui_service.lookup_vendor(mac)
            assert vendor == expected_vendor, f"MAC {mac}: expected {expected_vendor}, got {vendor}"

    def test_oui_normalize_mac_colons(self, oui_service):
        """Test MAC normalization with colons"""
        # Access private method for testing
        normalized = oui_service._normalize_mac("001A:2B:DD:EE:FF")
        assert normalized == "001A2BDDEEFF"

    def test_oui_normalize_mac_hyphens(self, oui_service):
        """Test MAC normalization with hyphens"""
        normalized = oui_service._normalize_mac("001A-2B-DD-EE-FF")
        assert normalized == "001A2BDDEEFF"

    def test_oui_normalize_mac_dots(self, oui_service):
        """Test MAC normalization with dots"""
        normalized = oui_service._normalize_mac("001A.2B.DD.EE.FF")
        assert normalized == "001A2BDDEEFF"
