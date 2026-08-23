from app import tasks
from app.tasks import _base_protein_name, _inhibited_defence, _parse_domtblout

# domtblout columns used by _parse_domtblout (0-indexed):
#   0 target(seq) name, 3 query(profile) name, 6 e-value, 7 score,
#   15 hmm-from, 16 hmm-to, 17 ali-from, 18 ali-to
DOMTBLOUT_HEADER_COMMENT = "# this is a comment line and should be ignored\n"


def _line(name, profile, evalue, score, hmm_from, hmm_to, ali_from, ali_to):
    fields = [name, "-", "100", profile, "-", "50", str(evalue), str(score), "0.1"]
    fields += ["1", "1", str(evalue), str(evalue), str(score), "0.1"]
    fields += [str(hmm_from), str(hmm_to), str(ali_from), str(ali_to)]
    fields += ["1", "60", "0.9", "some description"]
    return " ".join(fields) + "\n"


def test_parse_domtblout_sorts_by_evalue_ascending(tmp_path):
    domtblout = tmp_path / "hits.domtblout"
    domtblout.write_text(
        DOMTBLOUT_HEADER_COMMENT
        + _line("query1", "profileA", "1e-10", "55.2", 10, 60, 5, 55)
        + _line("query2", "profileB", "1e-20", "80.1", 20, 70, 15, 65)
    )

    hits = _parse_domtblout(domtblout)

    assert len(hits) == 2
    assert hits[0]["query_name"] == "query2"  # more significant e-value comes first
    assert hits[0]["evalue"] == 1e-20
    assert hits[1]["query_name"] == "query1"
    assert hits[1]["adp"] == "profileA"
    assert hits[1]["hmm_from"] == 10
    assert hits[1]["ali_to"] == 55


def test_parse_domtblout_skips_short_and_comment_lines(tmp_path):
    domtblout = tmp_path / "hits.domtblout"
    domtblout.write_text(
        "# comment\n"
        "too short a line\n"
        + _line("query1", "profileA", "1e-10", "55.2", 10, 60, 5, 55)
    )

    hits = _parse_domtblout(domtblout)

    assert len(hits) == 1
    assert hits[0]["query_name"] == "query1"


def test_base_protein_name_strips_nmr_model_suffix():
    assert _base_protein_name("klca_MODEL_16_A") == "klca"
    assert _base_protein_name("klca_MODEL_1_B") == "klca"


def test_base_protein_name_leaves_plain_names_unchanged():
    assert _base_protein_name("some_protein") == "some_protein"


def test_parse_domtblout_strips_aln_suffix_from_profile_name(tmp_path):
    domtblout = tmp_path / "hits.domtblout"
    domtblout.write_text(
        DOMTBLOUT_HEADER_COMMENT
        + _line("query1", "pnk.aln", "1e-10", "55.2", 10, 60, 5, 55)
    )

    hits = _parse_domtblout(domtblout)

    assert hits[0]["adp"] == "pnk"


def test_inhibited_defence_looks_up_metadata_tsv(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata.tsv"
    metadata.write_text("ID\tDefences\npnk\tPrrC\nno_defence\t_\n")
    monkeypatch.setattr(tasks, "METADATA_TSV", metadata)
    tasks._load_metadata.cache_clear()

    assert _inhibited_defence("pnk") == "PrrC"
    assert _inhibited_defence("no_defence") == ""
    assert _inhibited_defence("unknown_id") == ""

    tasks._load_metadata.cache_clear()
