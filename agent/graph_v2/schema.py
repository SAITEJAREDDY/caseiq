"""Phase 4 graph schema: constraints + indexes. Idempotent (IF NOT EXISTS),
safe to run on every build.

Canonical-id uniqueness constraints, one per node label that has a natural
source id. Two extra constraints exist for Hypothesis/ResolutionAttempt
because those tables are cross-referenced by their *own* native id
(diagnostic_hypotheses.id, resolution_attempts.id) from other Phase 3 tables
(hypothesis_evidence.hypothesis_id, resolution_attempts.targeted_hypothesis_id,
mitigations.resolution_attempt_id), while the node's primary key for the
InvestigationEvent layer is event_id (see loaders/investigation.py).
"""

CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Customer)              REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Case)                  REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Product)               REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ProductVersion)        REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Component)             REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:IssueCategory)         REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:IssueSubcategory)      REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Symptom)               REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Team)                  REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Skill)                 REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Agent)                 REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:KnowledgeArticle)      REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:RootCauseFamily)       REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ResolutionType)        REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ExternalService)       REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SupportPlan)           REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SLAPolicy)             REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:AgentShift)            REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ChangeEvent)           REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Incident)              REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ServiceHealthEvent)    REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ConfigurationSnapshot) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SignalType)            REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:CaseSignalObservation) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:TelemetryFinding)      REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:InvestigationEvent)    REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Hypothesis)            REQUIRE n.native_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ResolutionAttempt)     REQUIRE n.native_id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS FOR (n:InvestigationEvent) ON (n.case_id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:InvestigationEvent) ON (n.timestamp)",
    "CREATE INDEX IF NOT EXISTS FOR (n:ChangeEvent)        ON (n.started_at)",
    "CREATE INDEX IF NOT EXISTS FOR (n:ChangeEvent)        ON (n.component_id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Incident)           ON (n.started_at)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Incident)           ON (n.component_id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:CaseSignalObservation) ON (n.case_id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:CaseSignalObservation) ON (n.timestamp)",
    "CREATE INDEX IF NOT EXISTS FOR (n:TelemetryFinding)   ON (n.case_id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:ConfigurationSnapshot) ON (n.case_id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Case)               ON (n.created_date)",
]


def apply(session):
    for stmt in CONSTRAINTS:
        session.run(stmt)
    for stmt in INDEXES:
        session.run(stmt)
    print(f"  schema: {len(CONSTRAINTS)} constraints, {len(INDEXES)} indexes applied")
