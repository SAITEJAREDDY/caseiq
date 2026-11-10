"""Case-Case similarity, reusing Phase 1's own similar_cases.csv directly --
never an independently invented similarity metric."""
from agent.graph_v2.config import DATA_RAW_V2
from agent.graph_v2.db import read_csv, run_batched


def load(session):
    rows = read_csv(DATA_RAW_V2 / "similar_cases.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (a:Case {id: r.case_id_a})
        MATCH (b:Case {id: r.case_id_b})
        MERGE (a)-[rel:SIMILAR_TO]-(b)
        SET rel.similarity_score = toFloat(r.similarity_score)
        """,
        "Case-SIMILAR_TO",
    )
