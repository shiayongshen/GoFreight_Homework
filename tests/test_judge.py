from dc_nl_cli.judge import ResolutionJudge
from dc_nl_cli.parser.schema import CanonicalPayload
from dc_nl_cli.resolution import ResolutionEvidence
from dc_nl_cli.time_analysis import TimeSignals


def test_judge_accepts_population_query() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": "USA",
            "metric_query": "population",
            "time": {"type": "year", "value": "2020"},
        }
    )
    result = ResolutionJudge().judge(
        user_query="What was the population of USA in 2020?",
        canonical_payload=payload,
        resolved_query={
            "place": "country/USA",
            "stat_var": "Count_Person",
            "date": "2020",
        },
        stat_var_evidence=ResolutionEvidence(
            selected="Count_Person",
            selected_type="StatisticalVariable",
            selected_score=0.89,
            candidates=[
                {
                    "dcid": "Count_Person",
                    "typeOf": ["StatisticalVariable"],
                    "metadata": {"score": "0.89", "sentence": "population count"},
                }
            ],
        ),
    )
    assert result.decision == "accept"


def test_judge_warns_on_missing_place() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": None,
            "metric_query": "GDP",
            "time": {"type": "year", "value": "2020"},
        }
    )
    result = ResolutionJudge().judge(
        user_query="GDP in 2020",
        canonical_payload=payload,
        resolved_query={
            "place": None,
            "stat_var": "Amount_EconomicActivity_GrossDomesticProduction_Nominal",
            "date": "2020",
        },
    )
    assert result.decision == "warn"
    assert "missing_place" in result.reason_codes


def test_judge_rejects_unsupported_metric_resolution() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": "Taiwan",
            "metric_query": "happiness",
            "time": {"type": "year", "value": "2020"},
        }
    )
    result = ResolutionJudge().judge(
        user_query="How happy was Taiwan in 2020?",
        canonical_payload=payload,
        resolved_query={
            "place": "country/TWN",
            "stat_var": "LifeExpectancy_Person",
            "date": "2020",
        },
        stat_var_evidence=ResolutionEvidence(
            selected="LifeExpectancy_Person",
            selected_type="StatisticalVariable",
            selected_score=0.72,
            candidates=[
                {
                    "dcid": "LifeExpectancy_Person",
                    "typeOf": ["StatisticalVariable"],
                    "metadata": {"score": "0.72", "sentence": "people life expectancy"},
                }
            ],
        ),
    )
    assert result.decision == "reject"
    assert "low_metric_relevance" in result.reason_codes


def test_judge_rejects_topic_stat_var() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": "Taiwan",
            "metric_query": "goodness",
            "time": {"type": "year", "value": "2025"},
        }
    )
    result = ResolutionJudge().judge(
        user_query="How good in taiwan in 2025",
        canonical_payload=payload,
        resolved_query={
            "place": "country/TWN",
            "stat_var": "dc/topic/Health",
            "date": "2025",
        },
    )
    assert result.decision == "reject"
    assert "topic_instead_of_stat_var" in result.reason_codes


def test_judge_uses_candidate_sentence_similarity() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": "USA",
            "metric_query": "population",
            "time": {"type": "year", "value": "2020"},
        }
    )
    result = ResolutionJudge().judge(
        user_query="What was the population of USA in 2020?",
        canonical_payload=payload,
        resolved_query={
            "place": "country/USA",
            "stat_var": "Count_Person",
            "date": "2020",
        },
        stat_var_evidence=ResolutionEvidence(
            selected="Count_Person",
            selected_type="StatisticalVariable",
            selected_score=0.89,
            candidates=[
                {
                    "dcid": "Count_Person",
                    "typeOf": ["StatisticalVariable"],
                    "metadata": {"score": "0.89", "sentence": "population count"},
                }
            ],
        ),
    )
    assert result.decision == "accept"


def test_judge_rejects_latest_and_year_conflict() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": "USA",
            "metric_query": "population",
            "time": {"type": "year", "value": "2020"},
        }
    )
    result = ResolutionJudge().judge(
        user_query="What was the latest population of USA in 2020?",
        canonical_payload=payload,
        resolved_query={
            "place": "country/USA",
            "stat_var": "Count_Person",
            "date": "2020",
        },
        time_signals=TimeSignals(
            signals=[
                {
                    "kind": "latest",
                    "value": None,
                    "start": None,
                    "end": None,
                    "modifier": None,
                },
                {
                    "kind": "year",
                    "value": "2020",
                    "start": None,
                    "end": None,
                    "modifier": None,
                },
            ]
        ),
    )
    assert result.decision == "reject"
    assert "conflicting_time_constraints" in result.reason_codes


def test_judge_rejects_range_and_year_conflict() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": "Japan",
            "metric_query": "unemployment rate",
            "time": {"type": "year", "value": "2018"},
        }
    )
    result = ResolutionJudge().judge(
        user_query="Show unemployment rate of Japan from 2015 to 2020 in 2018 only",
        canonical_payload=payload,
        resolved_query={
            "place": "country/JPN",
            "stat_var": "UnemploymentRate_Person",
            "date": "2018",
        },
        time_signals=TimeSignals(
            signals=[
                {
                    "kind": "range",
                    "value": None,
                    "start": "2015",
                    "end": "2020",
                    "modifier": None,
                },
                {
                    "kind": "year",
                    "value": "2018",
                    "start": None,
                    "end": None,
                    "modifier": "only",
                },
            ]
        ),
    )
    assert result.decision == "reject"
    assert "conflicting_time_constraints" in result.reason_codes


def test_judge_rejects_low_confidence_stat_var() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": "Japan",
            "metric_query": "economic strength",
            "time": {"type": "year", "value": "2020"},
        }
    )
    result = ResolutionJudge().judge(
        user_query="economic strength of Japan in 2020",
        canonical_payload=payload,
        resolved_query={
            "place": "country/JPN",
            "stat_var": "Amount_EconomicActivity_GrossDomesticProduction_Nominal",
            "date": "2020",
        },
        stat_var_evidence=ResolutionEvidence(
            selected="Amount_EconomicActivity_GrossDomesticProduction_Nominal",
            selected_type="StatisticalVariable",
            selected_score=0.51,
            candidates=[
                {
                    "dcid": "Amount_EconomicActivity_GrossDomesticProduction_Nominal",
                    "typeOf": ["StatisticalVariable"],
                    "metadata": {"score": "0.51"},
                }
            ],
        ),
    )
    assert result.decision == "reject"
    assert "low_stat_var_confidence" in result.reason_codes
