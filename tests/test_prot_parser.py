from prot_parser import VoteringResult, ProtParser


class TestRmToYear:
    def test_single_year(self):
        assert ProtParser.rm_to_year("1971") == 1971

    def test_single_year_1867(self):
        assert ProtParser.rm_to_year("1867") == 1867

    def test_slash_year(self):
        assert ProtParser.rm_to_year("1975/76") == 1975

    def test_slash_year_modern(self):
        assert ProtParser.rm_to_year("2002/03") == 2002

    def test_slash_year_century_boundary(self):
        assert ProtParser.rm_to_year("1999/00") == 1999

    def test_invalid_returns_0(self):
        assert ProtParser.rm_to_year("okänd") == 0


class TestParseOcrProse:
    def setup_method(self):
        self.parser = ProtParser()

    def test_pattern_a_explicit_counts(self):
        text = """
        Vid omröstning genom omröstningsapparat.
        Ja: 234   Nej: 57   Avstår: 7
        """
        result = self.parser._parse_ocr_prose(text)
        assert result is not None
        assert result.ja == 234
        assert result.nej == 57
        assert result.avstar == 7
        assert result.metod == "omröstning"

    def test_pattern_b_prose_sentence(self):
        text = "Utskottets hemställan bifölls med 151 röster mot 149 för reservationen."
        result = self.parser._parse_ocr_prose(text)
        assert result is not None
        assert result.ja == 151
        assert result.nej == 149
        assert result.avstar is None
        assert result.metod == "omröstning"

    def test_acclamation_no_numbers(self):
        text = "Utskottets hemställan bifölls."
        result = self.parser._parse_ocr_prose(text)
        assert result is not None
        assert result.metod == "acklamation"
        assert result.ja is None
        assert result.nej is None

    def test_ocr_noise_ja_with_space(self):
        # OCR sometimes splits "Ja" as "J a"
        text = "J a: 200  N ej: 30  Avstår: 5"
        result = self.parser._parse_ocr_prose(text)
        assert result is not None
        assert result.ja == 200
        assert result.nej == 30

    def test_no_voting_returns_none(self):
        text = "Riksdagen behandlade frågan om statsbudgeten."
        result = self.parser._parse_ocr_prose(text)
        assert result is None

    def test_partier_empty_for_era1(self):
        text = "Ja: 100  Nej: 50  Avstår: 0"
        result = self.parser._parse_ocr_prose(text)
        assert result.partier == {}

    def test_pattern_a_dotall_noise_between_tokens(self):
        # Noise between vote counts forces DOTALL path
        text = "Ja: 100\n[oläsligt text]\nNej: 50\n*\nAvstar: 5"
        result = self.parser._parse_ocr_prose(text)
        assert result is not None
        assert result.ja == 100
        assert result.nej == 50

    def test_acclamation_rejected_when_digits_present(self):
        # Corrupt text: "bifölls" with numbers but no "med" — should return None, not acklamation
        text = "bifölls 151 röster mot 149"
        result = self.parser._parse_ocr_prose(text)
        # Pattern B fails (no "med"), acklamation must NOT fire because digits present
        assert result is None

    def test_none_input_returns_none(self):
        assert self.parser._parse_ocr_prose(None) is None

    def test_empty_string_returns_none(self):
        assert self.parser._parse_ocr_prose("") is None


class TestParseSnabb:
    def setup_method(self):
        self.parser = ProtParser()

    def test_simple_vote(self):
        text = """
        Huvudvotering:
        268 för utskottet
        20 för res. 1
        1 avstod
        60 frånvarande
        """
        result = self.parser._parse_snabb(text)
        assert result is not None
        assert result.ja == 268
        assert result.nej == 20
        assert result.metod == "omröstning"

    def test_party_in_reservation(self):
        text = """
        166 för utskottet
        124 för res. 2 (m, kd)
        59 frånvarande
        """
        result = self.parser._parse_snabb(text)
        assert result is not None
        assert result.ja == 166
        assert result.nej == 124
        assert result.partier == {"m": "nej", "kd": "nej"}

    def test_multiple_reservations(self):
        text = """
        Förberedande votering:
        25 för res. 1 (nyd)
        12 för men. i motsv. del (v)
        251 avstod
        61 frånvarande

        Huvudvotering:
        268 för utskottet
        20 för res. 1 (nyd)
        1 avstod
        60 frånvarande
        """
        # Should parse the Huvudvotering block
        result = self.parser._parse_snabb(text)
        assert result is not None
        assert result.ja == 268
        assert result.nej == 20
        assert "nyd" in result.partier

    def test_utskottet_is_ja_side(self):
        text = "100 för utskottet\n50 för res. 3 (s)\n49 frånvarande"
        result = self.parser._parse_snabb(text)
        assert result.ja == 100
        assert result.nej == 50

    def test_no_voting_block_returns_none(self):
        text = "Riksdagen beslutade om statsbudgeten."
        result = self.parser._parse_snabb(text)
        assert result is None

    def test_party_names_lowercased(self):
        text = "200 för utskottet\n100 för res. 1 (M, KD, FP)"
        result = self.parser._parse_snabb(text)
        assert "m" in result.partier
        assert "kd" in result.partier
        assert "fp" in result.partier

    def test_crlf_line_endings(self):
        text = "268 för utskottet\r\n20 för res. 1\r\n1 avstod\r\n"
        result = self.parser._parse_snabb(text)
        assert result is not None
        assert result.ja == 268
        assert result.nej == 20

    def test_trailing_spaces_on_vote_lines(self):
        text = "268 för utskottet   \n20 för res. 1   \n"
        result = self.parser._parse_snabb(text)
        assert result is not None
        assert result.ja == 268

    def test_avstar_and_franvarande_populated(self):
        text = "268 för utskottet\n20 för res. 1\n1 avstod\n60 frånvarande\n"
        result = self.parser._parse_snabb(text)
        assert result.avstar == 1
        assert result.franvarande == 60

    def test_only_reservations_no_utskottet_returns_none(self):
        # Guard: nej > 0 but ja == 0 → None
        text = "50 för res. 1 (m)\n30 för res. 2 (kd)\n"
        result = self.parser._parse_snabb(text)
        assert result is None

    def test_none_input_returns_none(self):
        assert self.parser._parse_snabb(None) is None


class TestParseHtml:
    def setup_method(self):
        self.parser = ProtParser()

    HTML_FIXTURE = """
    <html><body>
    <table>
    <tr><th>Namn</th><th>Parti</th><th>Valkrets</th><th>Bänk</th><th>Typ</th><th>Röst</th></tr>
    <tr><td>Anna Andersson</td><td>s</td><td>Stockholm</td><td class="vcenter">1</td><td>sakfrågan</td><td class="vcenter">Ja</td></tr>
    <tr><td>Björn Berg</td><td>s</td><td>Göteborg</td><td class="vcenter">2</td><td>sakfrågan</td><td class="vcenter">Ja</td></tr>
    <tr><td>Carl Carlsson</td><td>m</td><td>Malmö</td><td class="vcenter">3</td><td>sakfrågan</td><td class="vcenter">Nej</td></tr>
    <tr><td>Diana Dahl</td><td>m</td><td>Uppsala</td><td class="vcenter">4</td><td>sakfrågan</td><td class="vcenter">Nej</td></tr>
    <tr><td>Erik Ek</td><td>v</td><td>Lund</td><td class="vcenter">5</td><td>sakfrågan</td><td class="vcenter">Ja</td></tr>
    <tr><td>Fatima Falk</td><td>kd</td><td>Linköping</td><td class="vcenter">6</td><td>sakfrågan</td><td class="vcenter">Frånvarande</td></tr>
    </table>
    </body></html>
    """

    def test_aggregate_counts(self):
        result = self.parser._parse_html(self.HTML_FIXTURE)
        assert result is not None
        assert result.ja == 3        # Anna, Björn, Erik
        assert result.nej == 2       # Carl, Diana
        assert result.avstar == 0
        assert result.franvarande == 1  # Fatima
        assert result.metod == "omröstning"

    def test_party_majority_vote(self):
        result = self.parser._parse_html(self.HTML_FIXTURE)
        # s: 2 Ja → "ja"
        assert result.partier.get("s") == "ja"
        # m: 2 Nej → "nej"
        assert result.partier.get("m") == "nej"
        # v: 1 Ja → "ja"
        assert result.partier.get("v") == "ja"
        # kd: 1 Frånvarande → not in partier (or "frånvarande")
        assert "kd" not in result.partier or result.partier["kd"] == "frånvarande"

    def test_empty_table_returns_none(self):
        html = "<html><body><table></table></body></html>"
        result = self.parser._parse_html(html)
        assert result is None

    def test_no_table_returns_none(self):
        result = self.parser._parse_html("<html><body>Ingen votering</body></html>")
        assert result is None

    def test_ascii_vote_spellings_counted_in_party_tally(self):
        # Verify ASCII vote forms ("avstar", "franvarande") are normalised
        html = """<html><body><table>
        <tr><th>Namn</th><th>Parti</th><th>Valkrets</th><th>Bänk</th><th>Typ</th><th>Röst</th></tr>
        <tr><td>Anna</td><td>s</td><td>X</td><td>1</td><td>sakfrågan</td><td>Ja</td></tr>
        <tr><td>Björn</td><td>m</td><td>X</td><td>2</td><td>sakfrågan</td><td>Avstar</td></tr>
        </table></body></html>"""
        result = self.parser._parse_html(html)
        assert result is not None
        assert result.avstar == 1
        # m party voted Avstar → should appear in partier as "avstår"
        assert result.partier.get("m") == "avstår"


class TestParseVoteringDispatch:
    def setup_method(self):
        self.parser = ProtParser()

    def test_routes_era1_by_rm(self):
        text = "Ja: 100  Nej: 50  Avstår: 0"
        result = self.parser.parse_votering(text, "1980/81")
        assert result is not None
        assert result.ja == 100

    def test_routes_era2_by_rm(self):
        text = "100 för utskottet\n50 för res. 1 (m)"
        result = self.parser.parse_votering(text, "1996/97")
        assert result is not None
        assert result.ja == 100

    def test_routes_era3_by_rm(self):
        html = """<table>
        <tr><td>Anna</td><td>s</td><td>Stockholm</td><td>1</td><td>sakfrågan</td><td>Ja</td></tr>
        </table>"""
        result = self.parser.parse_votering(html, "2010/11")
        assert result is not None
        assert result.ja == 1

    def test_pre_1971_returns_none(self):
        result = self.parser.parse_votering("Någon text", "1965")
        assert result is None

    def test_unknown_rm_returns_none(self):
        result = self.parser.parse_votering("Text", "okänd")
        assert result is None


from historical_import import format_votering_for_commit


class TestFormatVoteringForCommit:
    def test_full_result_with_parties(self):
        v = VoteringResult(
            ja=268, nej=20, avstar=1, franvarande=60,
            partier={"s": "ja", "mp": "ja", "m": "nej"},
            metod="omröstning", källa="GQ19KU2"
        )
        s = format_votering_for_commit(v)
        assert "268 ja" in s
        assert "20 nej" in s
        assert "1 avstår" in s

    def test_acclamation(self):
        v = VoteringResult(
            metod="acklamation", källa="prot 1980:50 §3"
        )
        assert format_votering_for_commit(v) == "acklamation"

    def test_none_returns_ej_tillganglig(self):
        assert format_votering_for_commit(None) == "ej tillgänglig"

    def test_parties_sorted_in_output(self):
        v = VoteringResult(
            ja=100, nej=50, avstar=0, franvarande=10,
            partier={"m": "nej", "s": "ja", "v": "ja"},
            metod="omröstning"
        )
        s = format_votering_for_commit(v)
        assert "(s, v ja; m nej)" in s
