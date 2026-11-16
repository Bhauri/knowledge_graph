from __future__ import annotations

from random import choice, randint

from faker import Faker


MEDICAL_SITES = [
    "Plant A",
    "Plant B",
    "Plant C",
    "Regional Hub",
    "Supplier Facility",
    "Distribution Center",
]

SCENARIOS = [
    {
        "theme": "Sterility Assurance Drift",
        "focus": "manufacturing",
        "issue": "bioburden trend exceeded alert limits during aseptic filling of sterile product lots",
        "activity": "Production line inspection",
        "site": "Plant A",
        "product": "prefilled injectable syringe",
        "test": "bioburden monitoring",
        "category": "Production",
        "failure_code": "FC-101",
        "tool": "Microbiological trend review",
    },
    {
        "theme": "Seal Integrity Deviation",
        "focus": "manufacturing",
        "issue": "pouch seal strength drifted below validated acceptance criteria during final packaging",
        "activity": "Final quality audit",
        "site": "Plant B",
        "product": "sterile procedure kit",
        "test": "seal strength verification",
        "category": "Quality",
        "failure_code": "FC-102",
        "tool": "Packaging parameter review",
    },
    {
        "theme": "Particulate Customer Complaint",
        "focus": "customer",
        "issue": "customer reported visible particulate inside a finished medical device package",
        "activity": "Customer complaint review",
        "site": "Distribution Center",
        "product": "single-use infusion set",
        "test": "visual inspection verification",
        "category": "Customer",
        "failure_code": "FC-103",
        "tool": "Complaint triage review",
    },
    {
        "theme": "Cold Chain Excursion",
        "focus": "distribution",
        "issue": "shipment logger data showed temperature excursion outside qualified cold chain limits",
        "activity": "Distribution route review",
        "site": "Regional Hub",
        "product": "temperature-sensitive biologic cartridge",
        "test": "temperature logger review",
        "category": "Supplier",
        "failure_code": "FC-104",
        "tool": "Distribution excursion assessment",
    },
    {
        "theme": "Supplier Documentation Gap",
        "focus": "internal",
        "issue": "incoming component release records were incomplete for a critical sterile barrier component",
        "activity": "Incoming material review",
        "site": "Supplier Facility",
        "product": "implantable device component",
        "test": "incoming document verification",
        "category": "Supplier",
        "failure_code": "FC-105",
        "tool": "Supplier file audit",
    },
    {
        "theme": "Calibration Drift Investigation",
        "focus": "manufacturing",
        "issue": "torque station calibration drift created inconsistent assembly force readings on finished devices",
        "activity": "Process deviation check",
        "site": "Plant C",
        "product": "autoinjector assembly",
        "test": "torque calibration verification",
        "category": "Production",
        "failure_code": "FC-106",
        "tool": "Calibration drift analysis",
    },
]

MEDICAL_TERMS = [
    "batch release",
    "aseptic intervention",
    "device history record",
    "CAPA workflow",
    "traceability matrix",
    "change control",
    "line clearance",
    "complaint triage",
    "risk classification",
    "stability program",
    "sterile barrier",
    "environmental monitoring",
    "supplier qualification",
    "distribution hold",
]

OWNERS = [
    "Quality Engineering",
    "Manufacturing Operations",
    "Post-Market Surveillance",
    "Distribution Quality",
    "Supplier Quality",
]

ROOT_CAUSE_CATEGORIES = [
    "Equipment failure",
    "Human error",
    "Supplier issue",
    "Process variation",
    "Material defect",
    "Documentation control lapse",
]

STATUS_CHOICES = ["Open", "In Progress", "Under Review", "On Hold", "Closed"]


def word_count(text: str) -> int:
    return len(text.split())


def sample_scenario() -> dict[str, str]:
    return choice(SCENARIOS)


def medical_site() -> str:
    return choice(MEDICAL_SITES)


def medical_owner() -> str:
    return choice(OWNERS)


def root_cause_category() -> str:
    return choice(ROOT_CAUSE_CATEGORIES)


def themed_title(scenario: dict[str, str], suffix: str) -> str:
    return f"{scenario['theme']} - {suffix}"


def fit_word_range(fake: Faker, text: str, min_words: int, max_words: int) -> str:
    words = text.split()
    while len(words) < min_words:
        filler = (
            f"Additional review confirmed that {choice(MEDICAL_TERMS)} controls, escalation checkpoints, and documented approvals "
            f"for the {choice(MEDICAL_TERMS)} process remained under active medical quality oversight."
        )
        words.extend(filler.split())
        if len(words) < min_words:
            words.extend(fake.sentence(nb_words=16).split())

    if len(words) > max_words:
        words = words[:max_words]

    return " ".join(words).rstrip(" ,.;") + "."


def long_medical_text(
    fake: Faker,
    scenario: dict[str, str],
    section: str,
    min_words: int,
    max_words: int,
) -> str:
    product = scenario["product"]
    issue = scenario["issue"]
    activity = scenario["activity"].lower()
    site = scenario["site"]
    test_name = scenario["test"]
    term_a = choice(MEDICAL_TERMS)
    term_b = choice(MEDICAL_TERMS)
    term_c = choice(MEDICAL_TERMS)

    templates = {
        "qe_observation": (
            f"During {activity} at {site}, the quality team documented that {issue}. The affected product family was the {product}, "
            f"and the initial signal was escalated because the {test_name} record did not align with historical performance for comparable lots. "
            "Operators, line leaders, and quality reviewers compared lot history, equipment settings, sampling results, and material release records across shifts. "
            "The review identified variation in setup confirmation, inconsistent evidence of second-person verification, and delayed escalation after the first abnormal result was observed. "
            f"A temporary hold was placed on impacted inventory, in-process work was segregated, and downstream distribution checks were opened to protect patient safety. "
            f"Cross-functional interviews with manufacturing, engineering, microbiology, and supplier quality suggested the issue could involve a gap in {term_a}, "
            f"weakened execution of {term_b}, and incomplete confirmation of {term_c} before product disposition. "
            "Prior deviations with partially similar symptoms were sampled to determine whether this is an isolated event or a recurring quality signal that should trigger broader systemic action."
        ),
        "qe_expectation": (
            f"The expected condition is that every {product} lot is manufactured, inspected, released, and distributed under fully compliant medical quality system controls. "
            f"The {test_name} process should be executed exactly as validated, with all critical checkpoints independently verified and recorded before any release decision. "
            "Teams are expected to escalate abnormal findings immediately, quarantine potentially affected material without delay, and maintain complete traceability for components, operators, devices, and shipping units. "
            f"Management expects a data-supported root cause investigation that demonstrates whether the deviation arose from equipment, process discipline, supplier controls, training, or documentation execution in {term_a}. "
            "Corrective and preventive actions should be proportionate to patient and compliance risk, verified for effectiveness, and sustained through repeat monitoring, layered review, and management oversight. "
            "Any customer or regulatory communication must be accurate, timely, risk-based, and aligned with both pharmaceutical and medical device quality expectations before disposition is resumed."
        ),
        "psp_description": (
            f"This problem-solving record addresses a medical industry quality issue in which {issue}. The event affects the {product} workflow and was first detected during {activity.lower()} at {site}. "
            f"The description captures the operational context, the sequence of observations, and the immediate controls applied after the {test_name} signal became visible. "
            "Quality personnel confirmed that multiple lots, supporting records, and shift activities required comparison because the observed pattern did not match normal process behavior. "
            "The issue was considered significant due to possible impact on sterile assurance, complaint exposure, device performance, or release credibility depending on the material condition and product family involved. "
            f"The team documented manufacturing settings, material genealogy, inspection outcomes, sample retention history, environmental status, and open quality notifications linked to {term_a}. "
            "Containment included inventory hold, enhanced sampling, supervisor review of recent records, and communication to distribution or customer-facing teams where downstream exposure could not yet be excluded. "
            f"This description establishes the baseline problem statement that will guide investigation depth, risk review, and eventual CAPA decisions within the medical quality system."
        ),
        "psp_investigation": (
            f"The investigation for this medical quality issue focuses on why {issue} and whether the condition represents a local failure or a broader systemic weakness. "
            f"Investigators are reviewing machine parameters, setup sheets, operator training evidence, supplier documentation, sampling plans, complaint history, and {test_name} outputs from comparable lots. "
            "The working hypothesis includes potential equipment drift, ineffective verification at shift handover, delayed escalation, incomplete document review, or component variation introduced before final inspection. "
            f"The team is correlating quality data with {term_a}, {term_b}, and {term_c} checkpoints to determine whether controls were skipped, recorded late, or accepted without sufficient challenge. "
            "Interviews are being completed with line operators, quality engineers, supervisors, warehouse staff, and supplier quality representatives to validate the actual sequence of events against the approved process. "
            "Parallel record review is being used to compare stable lots with suspect lots so the group can isolate the failure mechanism, define exposure boundaries, and evaluate patient or customer risk with objective evidence. "
            "Findings from this investigation will support final risk classification, CAPA need, effectiveness strategy, and management communication within the broader medical industry compliance framework."
        ),
        "psp_summary": (
            f"The investigation summary concludes that the quality signal involving {issue} required coordinated review across manufacturing, quality, engineering, and distribution functions. "
            f"Evidence showed that the {test_name} signal was credible and that the affected {product} process contained documentation or execution weaknesses that reduced confidence in routine controls. "
            "The review narrowed the likely failure path to a combination of process discipline gaps, insufficient verification depth, and delayed recognition of abnormal conditions rather than a single isolated entry error. "
            f"Containment actions protected exposed material, expanded monitoring was applied, and traceability checks confirmed where additional review or market assessment was necessary. "
            f"Historical data also indicated that warning signs around {term_a} and {term_b} had appeared previously but were not escalated with sufficient rigor to trigger systemic correction. "
            "The summary therefore supports stronger oversight, clearer decision thresholds, retraining where needed, and corrective action plans that can be verified through subsequent lots, complaints, and trend reports. "
            "Overall, the record supports a medical industry conclusion that the event was manageable with decisive containment but still serious enough to justify CAPA consideration and continued effectiveness monitoring."
        ),
        "qe_event_description": (
            f"This event description documents a medical industry quality occurrence where {issue}. The event was associated with the {product} process and required formal escalation after signals observed during {activity.lower()} were confirmed by the {test_name} review. "
            "The event timeline includes the first detection point, the operator and reviewer decisions taken in real time, and the subsequent hold, segregation, or customer protection measures initiated to control exposure. "
            f"Multiple supporting records were examined, including manufacturing logs, quality review comments, supplier release information, sampling outcomes, environmental or handling conditions, and any connected deviations linked to {term_a}. "
            "Preliminary analysis suggested that normal barriers either did not detect the condition early enough or did not drive escalation fast enough to prevent broader operational impact. "
            f"Because the event could influence product safety, compliance posture, customer confidence, or distribution decisions, the case was tracked as a significant quality signal requiring complete documentation and management visibility. "
            "This record is intended to preserve the event context for downstream investigation, risk assessment, and action planning in the medical quality system."
        ),
        "capa_assessment": (
            f"The QA assessment for this CAPA addresses a medical industry issue in which {issue}. Reviewers determined that the affected {product} process cannot rely solely on immediate containment because the signal indicates potential weakness in system controls, execution discipline, or decision-making quality. "
            f"The assessment considers patient risk, complaint exposure, distribution impact, regulatory expectations, and repeatability of the observed failure across operations connected to {test_name}. "
            "Evidence reviewed includes deviation chronology, affected lot boundaries, complaint or field history, equipment condition, training records, material traceability, and management escalation quality. "
            f"The record also evaluates whether existing procedures for {term_a}, {term_b}, and {term_c} were sufficiently clear, consistently followed, and effective at detecting abnormal conditions before disposition. "
            "Based on current facts, quality assurance considers the issue serious enough to require sustained corrective action, explicit ownership, documented effectiveness criteria, and periodic review through closure. "
            "The CAPA is therefore justified not only to correct the immediate nonconformance, but also to strengthen the medical quality system so comparable events are detected earlier and controlled more reliably in future operations."
        ),
        "containment_assessment": (
            f"The containment assessment explains why immediate control measures were necessary after the team confirmed that {issue}. For the affected {product}, temporary actions were required to prevent additional manufacturing, distribution, or customer exposure while the formal investigation remained open. "
            f"Quality reviewed current inventory, work in process, retained samples, shipping status, and inspection evidence tied to {test_name} and related release checkpoints. "
            "The assessment determined that short-term containment needed to include segregation, enhanced review, decision controls on disposition, and clear communication to owners responsible for downstream operations. "
            f"This decision was supported by the possibility that weaknesses in {term_a} and {term_b} may have allowed the condition to persist longer than acceptable under medical industry standards. "
            "Containment will remain active until objective evidence confirms the exposure boundary, patient risk, and the adequacy of both immediate and permanent corrections."
        ),
        "action_description": (
            f"The action plan for this record addresses the medical quality signal where {issue}. Assigned teams will verify affected stock, review process settings, confirm document completeness, and evaluate whether additional customer or distribution protection steps are required for the {product}. "
            f"Execution includes targeted sampling, owner accountability, documented review of {test_name} evidence, and management checkpoints to ensure the action remains effective until final closure criteria are met. "
            "Where gaps are confirmed, retraining, procedure clarification, equipment intervention, supplier communication, or enhanced monitoring will be deployed with written evidence and due-date control."
        ),
        "initial_eval": (
            f"Initial evaluation indicates that {issue} may affect the {product} process and therefore requires medical industry review before routine disposition can continue. The available evidence suggests that process controls or review steps did not fully prevent, detect, or escalate the condition at the expected stage. "
            f"Current facts from {test_name}, lot history, and related records support continued assessment of patient, compliance, and customer risk while containment remains in place. "
            f"The issue is being evaluated against approved expectations for {term_a}, {term_b}, traceability quality, and response timeliness to determine whether broader systemic action is needed."
        ),
        "batch_material": (
            f"This batch contains {product} material associated with a medical quality review after the team confirmed that {issue}. The lot is held pending disposition while traceability, inspection evidence, and potential downstream exposure are reviewed."
        ),
        "deletion_comment": (
            f"Batch disposition record was flagged because review of {test_name} evidence and supporting quality documentation showed the material should not remain active pending resolution of the medical quality issue."
        ),
        "root_cause": (
            f"Most probable root cause is a combined weakness in process verification, escalation discipline, and documented review controls around {test_name}, which allowed {issue} to remain insufficiently challenged during normal operations."
        ),
        "justification": (
            f"CAPA and extended oversight are justified because the observed issue involves {product} quality controls with possible patient, compliance, or customer impact and cannot be closed with containment alone."
        ),
        "historical_parameter": (
            f"Historical review compared recent lots, complaint trends, and quality notifications related to {test_name} and found intermittent warning signals that now appear relevant to the current medical quality issue."
        ),
        "investigation_plan": (
            f"Investigation plan includes record review, owner interviews, targeted sampling, equipment or document verification, and comparison of stable versus affected lots to isolate why {issue} occurred in the {product} workflow."
        ),
        "test_description": (
            f"The test sequence evaluates the {product} against defined acceptance criteria using {test_name}. Samples from affected and unaffected lots are compared to confirm whether the observed issue is repeatable, isolated, or linked to broader process drift."
        ),
        "defect_description": (
            f"The defect item involves a medical quality concern where {issue}, creating uncertainty around product acceptability, release confidence, and downstream customer or distribution exposure."
        ),
    }

    return fit_word_range(fake, templates[section], min_words, max_words)


def random_testing_type() -> str:
    return choice(["Test", "Inspection", "Validation", "Verification"])


def random_specification() -> str:
    return choice([
        "Specification met",
        "Specification not met",
        "Pending review",
        "Awaiting evidence",
    ])


def random_event_status(closed: bool) -> str:
    if closed:
        return "Closed"
    return choice(STATUS_CHOICES)


def random_test_result() -> str:
    return choice(["Pass", "Fail", "Conditional Pass", "Blocked"])


def random_defer_item() -> str:
    return choice([
        "Hold and review impacted lots",
        "Escalate to quality council",
        "Suspend release pending evidence",
        "Continue quarantine until assessment closes",
        "Maintain enhanced inspection through next shift",
    ])


def testing_id() -> str:
    return f"TEST-{randint(10000, 99999)}"