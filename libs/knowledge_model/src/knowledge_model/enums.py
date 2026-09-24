from enum import Enum


class KnowledgeType(str, Enum):
    DECISION = "decision"
    FACT = "fact"
    CUSTOMER_INSIGHT = "customer_insight"
    STRATEGY = "strategy"
    PRODUCT_REQUIREMENT = "product_requirement"
    PROCESS = "process"
    POLICY = "policy"
    PERSON = "person"
    OWNERSHIP = "ownership"
    ACTION = "action"
    HYPOTHESIS = "hypothesis"
    CONFLICT = "conflict"


class KnowledgeStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONFLICTING = "conflicting"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"
