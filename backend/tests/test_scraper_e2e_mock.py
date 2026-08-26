import unittest
import json
import os
import requests
from unittest.mock import MagicMock
from legal_pipeline.scraper.engine import LegalScraperEngine

class TestScraperE2EMock(unittest.TestCase):
    def setUp(self):
        self.engine = LegalScraperEngine()
        # Mock the session's get method
        self.engine.indiacode.session.get = MagicMock()
        self.engine.kanoon.session.get = MagicMock()

    def test_complete_parse_and_json_structure(self):
        # Patch time.sleep to avoid waiting during tests
        import time
        time.sleep = MagicMock()

        # Mock IndiaCode failure
        self.engine.indiacode.session.get.return_value.status_code = 404
        
        # Mock Kanoon Success
        mock_search_html = """
        <div class="result_title"><a href="/doc/1028815/">Specific Relief Act, 1963</a></div>
        """
        mock_act_toc_html = """
        <div class="judgments">
            <a href="/doc/12345/">Section 1. Short title, extent and commencement</a>
            <a href="/doc/67890/">Section 2. Definitions</a>
            <a href="/doc/11111/">Section 3. Savings</a>
        </div>
        """
        mock_sec1_html = """
        <div class="doc_title">Section 1 in The Specific Relief Act, 1963</div>
        <div class="judgments">
            Section 1. Short title, extent and commencement. (1) This Act may be called the Specific Relief Act, 1963. 
            (2) It extends to the whole of India except the State of Jammu and Kashmir.
            (3) It shall come into force on such date as the Central Government may, by notification in the Official Gazette, appoint.
            Additional text to ensure the length is over 200 characters for validation purposes. 
            This is a mock section content designed to pass the quality checks implemented in the scraper engine.
        </div>
        """
        
        # Configure side effects for Kanoon requests
        def kanoon_side_effect(url, headers=None, timeout=None):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if "search" in url:
                mock_resp.text = mock_search_html
            elif "/doc/1028815/" in url:
                mock_resp.text = mock_act_toc_html
            elif "/doc/12345/" in url:
                mock_resp.text = mock_sec1_html
            else:
                mock_resp.status_code = 404
            return mock_resp

        self.engine.kanoon.session.get.side_effect = kanoon_side_effect

        # Run scrape
        sections, source = self.engine.scrape_act("Specific Relief Act")
        
        # Confirm Source
        self.assertEqual(source, "IndianKanoon")
        
        # Confirm Sections found
        self.assertGreater(len(sections), 0)
        
        # Confirm JSON Structure
        first_sec = sections[0]
        required_keys = ["section_number", "title", "text", "hash"]
        for key in required_keys:
            self.assertIn(key, first_sec)
            
        self.assertEqual(first_sec["section_number"], "1")
        self.assertIn("Short title", first_sec["title"])
        self.assertIn("Specific Relief Act", first_sec["text"])
        self.assertTrue(len(first_sec["hash"]) == 64) # SHA-256 length

        # Final verification of full JSON result structure
        result = {
            "act_name": "Specific Relief Act",
            "year": "1963",
            "source": source,
            "last_updated": "2026-03-16 21:00:00",
            "sections": sections
        }
        
        print("\n--- Verified JSON Structure ---")
        print(json.dumps(result, indent=2))
        print("--- End Verification ---\n")

if __name__ == "__main__":
    unittest.main()
