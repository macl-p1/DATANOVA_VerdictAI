from verdictai.labels import entity_types, load_labels


def test_labels_are_bio_pairs():
    labels = load_labels()
    assert labels[0] == "O"
    for kind in entity_types(labels):
        assert f"B-{kind}" in labels and f"I-{kind}" in labels
