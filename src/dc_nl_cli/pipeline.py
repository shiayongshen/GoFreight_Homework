from __future__ import annotations

from dataclasses import dataclass

from dc_nl_cli.config import Settings, load_settings
from dc_nl_cli.datacommons import DataCommonsClient, QueryBuilder
from dc_nl_cli.judge import ResolutionJudge
from dc_nl_cli.llm.base import LLMClient
from dc_nl_cli.llm.factory import build_llm_client
from dc_nl_cli.parser import QueryParser
from dc_nl_cli.resolvers import PlaceResolver, StatVarResolver, TimeResolver
from dc_nl_cli.time_analysis import TimeConstraintAnalyzer


@dataclass
class BaselinePipeline:
    parser: QueryParser
    place_resolver: PlaceResolver
    stat_var_resolver: StatVarResolver
    time_resolver: TimeResolver
    query_builder: QueryBuilder
    datacommons_client: DataCommonsClient
    judge: ResolutionJudge
    time_analyzer: TimeConstraintAnalyzer

    def run(self, query: str) -> dict:
        canonical_payload = self.parser.parse(query)
        time_signals = self.time_analyzer.analyze(query)
        stat_var_resolution = self.stat_var_resolver.resolve_with_evidence(
            canonical_payload.metric_query
        )
        stat_var_dcid = stat_var_resolution.selected
        time_query = self.time_resolver.resolve(canonical_payload.time)
        primary_place_dcid = None
        comparison_place_dcids: list[str] = []
        if not canonical_payload.place_query:
            partial_output = {
                "input": query,
                "canonical_payload": canonical_payload.model_dump(exclude_none=True),
                "resolved_query": {
                    "place": None,
                    "stat_var": stat_var_dcid,
                    "date": time_query["date"],
                },
                "result": None,
                "warning": "place was not specified; query was parsed but not executed",
            }
            partial_output["judge"] = self.judge.judge(
                user_query=query,
                canonical_payload=canonical_payload,
                resolved_query=partial_output["resolved_query"],
                time_signals=time_signals,
                stat_var_evidence=stat_var_resolution,
            ).to_dict()
            partial_output["resolution_evidence"] = {
                "stat_var": stat_var_resolution.to_dict(),
            }
            return partial_output

        primary_place_resolution = self.place_resolver.resolve_with_evidence(
            canonical_payload.place_query
        )
        primary_place_dcid = primary_place_resolution.selected
        if (
            canonical_payload.intent == "compare_places"
            and canonical_payload.comparison
        ):
            comparison_place_resolutions = [
                self.place_resolver.resolve_with_evidence(place_query)
                for place_query in canonical_payload.comparison.places
            ]
            comparison_place_dcids = [
                resolution.selected for resolution in comparison_place_resolutions
            ]
        resolved_query = self.query_builder.build(
            payload=canonical_payload,
            place_dcid=primary_place_dcid,
            stat_var_dcid=stat_var_dcid,
            date=time_query["date"],
            comparison_place_dcids=comparison_place_dcids,
        )
        judge_result = self.judge.judge(
            user_query=query,
            canonical_payload=canonical_payload,
            resolved_query=resolved_query,
            time_signals=time_signals,
            stat_var_evidence=stat_var_resolution,
        )
        if judge_result.decision == "reject":
            return {
                "input": query,
                "canonical_payload": canonical_payload.model_dump(exclude_none=True),
                "resolved_query": resolved_query,
                "result": None,
                "judge": judge_result.to_dict(),
                "resolution_evidence": {
                    "stat_var": stat_var_resolution.to_dict(),
                },
            }

        if (
            canonical_payload.intent == "compare_places"
            and canonical_payload.comparison
        ):
            all_places = [primary_place_dcid, *comparison_place_dcids]
            raw_results = [
                self.datacommons_client.get_observations(
                    place_dcid=place_dcid,
                    stat_var_dcid=stat_var_dcid,
                    date=time_query["date"],
                )
                for place_dcid in all_places
            ]
            place_results = [
                {
                    "place": place_dcid,
                    **self.query_builder.normalize_result(
                        raw_response=raw_result,
                        place_dcid=place_dcid,
                        stat_var_dcid=stat_var_dcid,
                        date=time_query["date"],
                    ),
                }
                for place_dcid, raw_result in zip(all_places, raw_results, strict=True)
            ]
            result = self.query_builder.aggregate_results(
                operation=canonical_payload.comparison.operation,
                place_results=place_results,
                date=time_query["date"],
            )
        else:
            raw_result = self.datacommons_client.get_observations(
                place_dcid=primary_place_dcid,
                stat_var_dcid=stat_var_dcid,
                date=time_query["date"],
            )
            result = self.query_builder.normalize_result(
                raw_response=raw_result,
                place_dcid=primary_place_dcid,
                stat_var_dcid=stat_var_dcid,
                date=time_query["date"],
            )
        return {
            "input": query,
            "canonical_payload": canonical_payload.model_dump(exclude_none=True),
            "resolved_query": resolved_query,
            "result": result,
            "judge": judge_result.to_dict(),
            "resolution_evidence": {
                "stat_var": stat_var_resolution.to_dict(),
            },
        }


def build_pipeline(
    settings: Settings | None = None, *, llm_client: LLMClient | None = None
) -> BaselinePipeline:
    settings = settings or load_settings()
    llm_client = llm_client if llm_client is not None else build_llm_client(settings)

    datacommons_client = DataCommonsClient(
        api_key=settings.datacommons_api_key,
        base_url=settings.datacommons_base_url,
        timeout=settings.request_timeout_seconds,
    )

    return BaselinePipeline(
        parser=QueryParser(llm_client=llm_client),
        place_resolver=PlaceResolver(datacommons_client, mode=settings.resolver_mode),
        stat_var_resolver=StatVarResolver(
            datacommons_client, mode=settings.resolver_mode
        ),
        time_resolver=TimeResolver(),
        query_builder=QueryBuilder(),
        datacommons_client=datacommons_client,
        judge=ResolutionJudge(),
        time_analyzer=TimeConstraintAnalyzer(llm_client=llm_client),
    )
