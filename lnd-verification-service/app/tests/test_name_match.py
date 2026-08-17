from app.services.name_match import match_score, is_match


def test_identical_names_score_high():
    assert match_score("Jahnavi Patel", "Jahnavi Patel") == 1.0


def test_close_names_are_a_match():
    # Middle initial / minor formatting differences shouldn't break the match.
    assert is_match("Jahnavi Patel", "jahnavi  patel", threshold=0.82)


def test_different_names_are_not_a_match():
    assert not is_match("Jahnavi Patel", "Alex Rivera", threshold=0.82)
