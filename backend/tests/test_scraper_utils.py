import unittest
from legal_pipeline.scraper.utils import clean_text, get_text_hash, is_valid_section

class TestScraperUtils(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(clean_text("  hello   world  "), "hello world")
        self.assertEqual(clean_text("line1\nline2"), "line1 line2")

    def test_get_text_hash(self):
        text = "test content"
        h1 = get_text_hash(text)
        h2 = get_text_hash(text)
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, get_text_hash("other content"))

    def test_is_valid_section(self):
        valid_text = "Section 45: This is a long enough text to be considered a valid section content. It needs to be over 200 characters to pass the check and help ensure quality."
        valid_text += " " * 100 # Ensure length > 200
        self.assertTrue(is_valid_section(valid_text))
        
        invalid_text = "Section 1: Too short."
        self.assertFalse(is_valid_section(invalid_text))
        
        no_keyword_text = "Just some text without the keyword."
        self.assertFalse(is_valid_section(no_keyword_text))

if __name__ == "__main__":
    unittest.main()
