"""arXiv-link mode: ids, text extraction, repository links and verdicts (standard library only)."""

from __future__ import annotations

import unittest

from agent import arxiv


class Ids(unittest.TestCase):
    def test_ids_and_links(self) -> None:
        self.assertEqual(arxiv.arxiv_id("2409.11363"), "2409.11363")
        self.assertEqual(arxiv.arxiv_id("https://arxiv.org/abs/2409.11363v2"), "2409.11363v2")
        self.assertEqual(arxiv.arxiv_id("https://arxiv.org/pdf/1901.01234.pdf"), "1901.01234")
        self.assertEqual(arxiv.arxiv_id("hep-th/9901001"), "hep-th/9901001")
        with self.assertRaises(ValueError):
            arxiv.arxiv_id("not a paper")


class Text(unittest.TestCase):
    def test_tables_keep_cells_apart_and_links_are_collected(self) -> None:
        parser = arxiv._TextOfHtml()
        parser.feed(
            "<html><script>var x=1</script><p>Code: <a href='https://github.com/a/b'>here</a></p>"
            "<table><tr><th>Model</th><th>Acc</th></tr><tr><td>Ours</td><td>91.2</td></tr></table></html>"
        )
        text = parser.text()
        self.assertIn("Ours | 91.2", text)
        self.assertNotIn("var x", text)
        self.assertEqual(parser.links, ["https://github.com/a/b"])

    def test_repository_comes_from_the_paper_first(self) -> None:
        meta = {"title": "T", "abstract": "no link"}
        repo, how = arxiv.find_repo(meta, "see https://github.com/owner/proj.git.", [])
        self.assertEqual(repo, "https://github.com/owner/proj")
        self.assertIn("paper text", how)


class Verdicts(unittest.TestCase):
    def test_rounding_of_the_claim_is_allowed(self) -> None:
        self.assertEqual(arxiv.verdict(91.2, 91.23)["verdict"], "reproduced")
        self.assertEqual(arxiv.verdict(91.2, 90.1)["verdict"], "differs")

    def test_percent_and_fraction_are_the_same_number(self) -> None:
        self.assertEqual(arxiv.verdict(97.22, 0.9722)["verdict"], "reproduced")
        self.assertEqual(arxiv.verdict(0.45, 45.0)["verdict"], "reproduced")

    def test_no_value_is_not_reproduced(self) -> None:
        self.assertEqual(arxiv.verdict(1.0, None)["verdict"], "not reproduced")
        self.assertEqual(arxiv.verdict(1.0, "n/a")["verdict"], "differs")


if __name__ == "__main__":
    unittest.main()
