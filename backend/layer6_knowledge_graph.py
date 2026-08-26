"""
SAULSGPT — LAYER 6: LEGAL KNOWLEDGE GRAPH
==========================================
Uses NetworkX to map relationships between Indian laws.
Acts as a post-retrieval context expander in Layer 2.

What it does:
→ Maps act replacements (IPC → BNS 2023)
→ Maps section relationships (IPC 302 → IPC 300)
→ Maps constitutional hierarchy
→ Maps procedure chains (FIR → Investigation → Trial)
→ Expands Layer 2 results with related law context

How it plugs in:
→ Called AFTER ChromaDB + BM25 retrieval
→ BEFORE Layer 3 reasoning
→ Returns graph insights as structured strings
→ Does NOT fake document chunks (avoids Layer 4 issues)

Run standalone to test:
    python layer6_knowledge_graph.py
"""

import networkx as nx
from typing import List, Dict

# ─────────────────────────────────────────────────────────────
# ACT NAME NORMALIZER
# Your ChromaDB stores act names in various formats
# This maps all variations to canonical graph node names
# ─────────────────────────────────────────────────────────────

ACT_ALIASES = {
    # IPC variations
    "ipc": "IPC",
    "indian penal code": "IPC",
    "indian penal code, 1860": "IPC",
    "indian penal code 1860": "IPC",
    "ipc_from_db": "IPC",

    # CrPC variations
    "crpc": "CrPC",
    "code of criminal procedure": "CrPC",
    "code of criminal procedure, 1973": "CrPC",
    "crpc_from_db": "CrPC",

    # Evidence Act variations
    "indian evidence act": "IEA",
    "indian evidence act, 1872": "IEA",
    "indian evidence act 1872": "IEA",
    "iea_from_db": "IEA",

    # New acts
    "bns 2023": "BNS",
    "bharatiya nyaya sanhita": "BNS",
    "bharatiya nyaya sanhita 2023": "BNS",

    "bnss 2023": "BNSS",
    "bharatiya nagarik suraksha sanhita": "BNSS",
    "bharatiya nagarik suraksha sanhita 2023": "BNSS",
    "bnss_from_db": "BNSS",

    "bsa 2023": "BSA",
    "bharatiya sakshya adhiniyam": "BSA",
    "bharatiya sakshya adhiniyam 2023": "BSA",

    # CPC
    "code of civil procedure": "CPC",
    "code of civil procedure, 1908": "CPC",
    "cpc_from_db": "CPC",

    # Constitution
    "constitution of india": "Constitution",
    "the constitution of india": "Constitution",
    "indian_constitution": "Constitution",

    # HMA
    "hindu marriage act": "HMA",
    "hindu marriage act, 1955": "HMA",
    "hma_from_db": "HMA",

    # Motor Vehicles
    "motor vehicles act": "MVA",
    "mva_from_db": "MVA",

    # NI Act
    "negotiable instruments act": "NIA",
    "nia_from_db": "NIA",

    # IDA
    "industrial disputes act": "IDA",
    "ida_from_db": "IDA",
}


def normalize_act_name(raw_name: str) -> str:
    """
    Converts raw ChromaDB act_name to canonical graph node name.

    Example:
        "Indian Penal Code, 1860" → "IPC"
        "crpc_from_db"            → "CrPC"
    """
    return ACT_ALIASES.get(raw_name.lower().strip(), raw_name)


# ─────────────────────────────────────────────────────────────
# KNOWLEDGE GRAPH CLASS
# ─────────────────────────────────────────────────────────────

class LegalKnowledgeGraph:
    """
    Directed graph of Indian law relationships.
    Built once at startup, queried for every user request.

    Node types:
    → Acts        : IPC, CrPC, BNS, Constitution etc
    → Sections    : IPC_302, CrPC_41, Article_21 etc
    → Concepts    : Cognizable_Offence, Murder, FIR etc
    → Procedures  : Arrest, Trial, Appeal etc

    Edge types (relations):
    → replaced_by       : IPC → BNS 2023
    → related_to        : IPC_302 → IPC_300
    → requires          : IPC_302 → IPC_300 (needs definition)
    → procedure_for     : CrPC_41 → Cognizable_Offence
    → overrides         : Constitution → all acts
    → lesser_offence    : IPC_302 → IPC_304
    → next_step         : FIR → Police_Investigation
    → struck_down       : IPC_124A → SC_Stay_2022
    → read_down         : IPC_377 → Navtej_Johar_2018
    """

    def __init__(self):
        print("[Graph] 🕸️  Initializing Legal Knowledge Graph...")
        self.G = nx.DiGraph()
        self._build_graph()
        print(f"[Graph] ✅ Graph built: "
              f"{self.G.number_of_nodes()} nodes, "
              f"{self.G.number_of_edges()} edges\n")

    def _build_graph(self):
        """
        Builds the complete legal relationship graph.
        Covers: act replacements, section mappings,
        constitutional hierarchy, procedure chains,
        struck down sections.
        """

        # ── ACT LEVEL REPLACEMENTS ──
        # July 1 2024 — three major laws replaced
        self.G.add_edge("IPC",  "BNS",  relation="replaced_by", date="2024-07-01")
        self.G.add_edge("CrPC", "BNSS", relation="replaced_by", date="2024-07-01")
        self.G.add_edge("IEA",  "BSA",  relation="replaced_by", date="2024-07-01")

        # ── CONSTITUTIONAL HIERARCHY ──
        self.G.add_edge("Constitution", "IPC",  relation="overrides")
        self.G.add_edge("Constitution", "CrPC", relation="overrides")
        self.G.add_edge("Constitution", "BNS",  relation="overrides")
        self.G.add_edge("Constitution", "BNSS", relation="overrides")
        self.G.add_edge("Article_21",   "IPC",  relation="fundamental_right_override")
        self.G.add_edge("Article_21",   "CrPC", relation="fundamental_right_override")
        self.G.add_edge("Article_14",   "IPC",  relation="fundamental_right_override")
        self.G.add_edge("Article_22",   "CrPC", relation="governs")

        # ── CRIMINAL LAW SECTION MAPPINGS ──

        # Murder
        self.G.add_edge("IPC_302", "BNS_103",  relation="replaced_by")
        self.G.add_edge("IPC_302", "IPC_300",  relation="requires_definition_from")
        self.G.add_edge("IPC_302", "IPC_299",  relation="distinguished_from")
        self.G.add_edge("IPC_302", "IPC_304",  relation="lesser_offence")
        self.G.add_edge("IPC_302", "Article_21", relation="constitutional_angle")
        self.G.add_edge("IPC_302", "CrPC_41",  relation="arrest_under")

        # Theft and related
        self.G.add_edge("IPC_378", "BNS_303",  relation="replaced_by")
        self.G.add_edge("IPC_379", "IPC_378",  relation="requires_definition_from")
        self.G.add_edge("IPC_379", "BNS_304",  relation="replaced_by")

        # Cheating
        self.G.add_edge("IPC_420", "BNS_318",  relation="replaced_by")
        self.G.add_edge("IPC_415", "IPC_420",  relation="defines")

        # Hurt and assault
        self.G.add_edge("IPC_319", "IPC_321",  relation="lesser_offence")
        self.G.add_edge("IPC_320", "IPC_322",  relation="grievous_hurt")
        self.G.add_edge("IPC_323", "BNS_115",  relation="replaced_by")

        # Sexual offences
        self.G.add_edge("IPC_375", "BNS_63",   relation="replaced_by")
        self.G.add_edge("IPC_376", "BNS_64",   relation="replaced_by")

        # Kidnapping
        self.G.add_edge("IPC_359", "IPC_360",  relation="defines_type")
        self.G.add_edge("IPC_359", "IPC_361",  relation="defines_type")
        self.G.add_edge("IPC_363", "BNS_137",  relation="replaced_by")

        # ── STRUCK DOWN / READ DOWN SECTIONS ──
        self.G.add_edge("IPC_377",  "Navtej_Johar_2018",   relation="read_down")
        self.G.add_edge("IPC_124A", "Vombatkere_SC_Stay",  relation="under_stay")
        self.G.add_edge("IPC_303",  "Mithu_Punjab_1983",   relation="struck_down")
        self.G.add_edge("ITA_66A",  "Shreya_Singhal_2015", relation="struck_down")

        # ── ARREST PROCEDURE CHAIN ──
        self.G.add_edge("CrPC_41",  "BNSS_35",   relation="replaced_by")
        self.G.add_edge("CrPC_41",  "Article_22", relation="subject_to")
        self.G.add_edge("CrPC_46",  "BNSS_43",   relation="replaced_by")
        self.G.add_edge("CrPC_50",  "BNSS_47",   relation="replaced_by")
        self.G.add_edge("CrPC_57",  "BNSS_58",   relation="replaced_by")

        # ── FIR PROCEDURE CHAIN ──
        self.G.add_edge("FIR",         "CrPC_154",           relation="filed_under")
        self.G.add_edge("CrPC_154",    "BNSS_173",           relation="replaced_by")
        self.G.add_edge("FIR",         "Police_Investigation", relation="triggers")
        self.G.add_edge("Police_Investigation", "Chargesheet", relation="leads_to")
        self.G.add_edge("Chargesheet", "CrPC_173",           relation="filed_under")
        self.G.add_edge("CrPC_173",    "BNSS_193",           relation="replaced_by")
        self.G.add_edge("Chargesheet", "Magistrate_Cognizance", relation="leads_to")
        self.G.add_edge("Magistrate_Cognizance", "Trial",    relation="leads_to")
        self.G.add_edge("Trial",        "Judgment",           relation="leads_to")
        self.G.add_edge("Judgment",     "Appeal",             relation="appealable_in")

        # ── BAIL PROCEDURE ──
        self.G.add_edge("CrPC_436",  "BNSS_478",  relation="replaced_by")
        self.G.add_edge("CrPC_437",  "BNSS_479",  relation="replaced_by")
        self.G.add_edge("CrPC_438",  "BNSS_482",  relation="replaced_by")
        self.G.add_edge("CrPC_439",  "BNSS_483",  relation="replaced_by")
        self.G.add_edge("CrPC_436",  "Bailable_Offence",     relation="applies_to")
        self.G.add_edge("CrPC_437",  "Non_Bailable_Offence", relation="applies_to")
        self.G.add_edge("CrPC_438",  "Anticipatory_Bail",    relation="provides_for")

        # ── CIVIL PROCEDURE CHAIN ──
        self.G.add_edge("CPC_Suit",   "CPC_Summons",  relation="triggers")
        self.G.add_edge("CPC_Summons","CPC_Written_Statement", relation="leads_to")
        self.G.add_edge("CPC_Written_Statement", "CPC_Trial", relation="leads_to")
        self.G.add_edge("CPC_Trial",  "CPC_Decree",   relation="leads_to")
        self.G.add_edge("CPC_Decree", "CPC_Appeal",   relation="appealable_in")

        # ── CONSUMER PROTECTION ──
        self.G.add_edge("Consumer_Protection_Act", "District_Commission", relation="complaint_to")
        self.G.add_edge("District_Commission",     "State_Commission",    relation="appeal_to")
        self.G.add_edge("State_Commission",        "National_Commission", relation="appeal_to")

        # ── LABOUR LAW ──
        self.G.add_edge("Payment_of_Wages_Act_S5",  "Payment_of_Wages_Act_S15", relation="claim_under")
        self.G.add_edge("Payment_of_Wages_Act_S15", "Labour_Court",             relation="filed_before")
        self.G.add_edge("Minimum_Wages_Act_S22",    "Labour_Court",             relation="filed_before")

    # ─────────────────────────────────────────────────────────
    # SECTION NODE BUILDER
    # ─────────────────────────────────────────────────────────

    def _build_section_node(self, act_name: str, section_num: str) -> str:
        """
        Builds the canonical section node name from ChromaDB metadata.

        Examples:
            ("IPC", "302")          → "IPC_302"
            ("CrPC", "41")          → "CrPC_41"
            ("Constitution", "21")  → "Article_21"
        """
        canonical_act = normalize_act_name(act_name)

        if canonical_act == "Constitution":
            return f"Article_{section_num}"
        elif canonical_act == "Information Technology Act":
            return f"ITA_{section_num}"
        else:
            return f"{canonical_act}_{section_num}"

    # ─────────────────────────────────────────────────────────
    # MAIN EXPANSION FUNCTION
    # ─────────────────────────────────────────────────────────

    def expand_context(self, retrieved_results: list) -> List[str]:
        """
        Takes Layer 2 ChromaDB results and traverses the graph
        to find all related law relationships.

        Returns structured insight strings that Layer 3 uses
        as additional context — NOT fake document chunks.

        Args:
            retrieved_results: list of dicts from layer2_retrieval
                              each with act_name, section_number

        Returns:
            list of human readable insight strings
            e.g. ["IPC has been replaced by BNS 2023 from July 1 2024"]

        Example:
            results = [{"act_name": "IPC", "section_number": "302"}]
            insights = graph.expand_context(results)
            # ["IPC has been replaced by BNS 2023",
            #   "IPC Section 302 requires definition from IPC Section 300",
            #   "Article 21 (Right to Life) overrides criminal statutes"]
        """
        insights = []
        seen     = set()

        # Check if any criminal act is involved
        # If yes — always add Article 21 context
        criminal_acts = {"IPC", "CrPC", "BNS", "BNSS"}
        retrieved_canonical = {
            normalize_act_name(r.get("act_name", ""))
            for r in retrieved_results
        }

        if retrieved_canonical & criminal_acts:
            insight = (
                "Constitutional Context: Article 21 (Right to Life and "
                "Personal Liberty) overrides all criminal procedural statutes. "
                "Every accused has constitutional rights that cannot be violated."
            )
            if insight not in seen:
                insights.append(insight)
                seen.add(insight)

        for item in retrieved_results:
            raw_act = item.get("act_name", "")
            sec_num = item.get("section_number", "")
            canonical_act = normalize_act_name(raw_act)

            # ── Check act-level relationships ──
            if self.G.has_node(canonical_act):
                for neighbor in self.G.successors(canonical_act):
                    edge_data = self.G.edges[canonical_act, neighbor]
                    relation  = edge_data.get("relation", "related_to")
                    date      = edge_data.get("date", "")

                    insight = self._format_insight(
                        canonical_act, relation, neighbor, date
                    )
                    if insight and insight not in seen:
                        insights.append(insight)
                        seen.add(insight)

            # ── Check section-level relationships ──
            if sec_num:
                section_node = self._build_section_node(raw_act, sec_num)
                if self.G.has_node(section_node):
                    for neighbor in self.G.successors(section_node):
                        edge_data = self.G.edges[section_node, neighbor]
                        relation  = edge_data.get("relation", "related_to")

                        insight = self._format_insight(
                            section_node, relation, neighbor
                        )
                        if insight and insight not in seen:
                            insights.append(insight)
                            seen.add(insight)

        return insights

    def _format_insight(
        self,
        source: str,
        relation: str,
        target: str,
        date: str = ""
    ) -> str:
        """
        Formats a graph edge into a human readable insight string.

        Args:
            source  : source node name
            relation: edge relation type
            target  : target node name
            date    : optional effective date

        Returns:
            human readable insight string
        """
        source_clean = source.replace("_", " ")
        target_clean = target.replace("_", " ")
        date_str     = f" (effective {date})" if date else ""

        RELATION_TEMPLATES = {
            "replaced_by": (
                f"⚠️  LAW UPDATE: {source_clean} has been replaced by "
                f"{target_clean}{date_str}. Please refer to current legislation."
            ),
            "requires_definition_from": (
                f"📖 DEFINITION: {source_clean} requires reading with "
                f"{target_clean} for complete understanding."
            ),
            "lesser_offence": (
                f"⚖️  RELATED OFFENCE: {source_clean} has a lesser offence "
                f"under {target_clean}."
            ),
            "distinguished_from": (
                f"⚖️  DISTINCTION: {source_clean} must be distinguished from "
                f"{target_clean}."
            ),
            "procedure_for": (
                f"📋 PROCEDURE: {source_clean} provides the procedure for "
                f"{target_clean}."
            ),
            "arrest_under": (
                f"🚔 ARREST: Offences under {source_clean} are arrested "
                f"under {target_clean}."
            ),
            "subject_to": (
                f"⚖️  CONSTITUTIONAL LIMIT: {source_clean} is subject to "
                f"{target_clean}."
            ),
            "overrides": (
                f"🏛️  HIERARCHY: {source_clean} overrides {target_clean}."
            ),
            "fundamental_right_override": (
                f"🏛️  FUNDAMENTAL RIGHT: {source_clean} protects citizens "
                f"against arbitrary application of {target_clean}."
            ),
            "struck_down": (
                f"🚨 INVALID LAW: {source_clean} was struck down by Supreme "
                f"Court in {target_clean}. This provision is no longer valid."
            ),
            "read_down": (
                f"🚨 MODIFIED LAW: {source_clean} was read down by Supreme "
                f"Court in {target_clean}. Partial decriminalization applies."
            ),
            "under_stay": (
                f"⚠️  SC STAY: {source_clean} is currently under Supreme "
                f"Court stay in {target_clean}. Not enforceable."
            ),
            "leads_to": (
                f"➡️  NEXT STEP: {source_clean} leads to {target_clean} "
                f"in the legal process."
            ),
            "triggers": (
                f"➡️  TRIGGERS: {source_clean} triggers {target_clean}."
            ),
        }

        return RELATION_TEMPLATES.get(
            relation,
            f"📌 RELATED: {source_clean} is {relation.replace('_',' ')} "
            f"{target_clean}{date_str}."
        )

    def get_procedure_chain(self, start_node: str) -> List[str]:
        """
        Returns the full procedure chain starting from a node.
        Useful for Path Finder mode.

        Args:
            start_node: starting concept e.g. "FIR"

        Returns:
            ordered list of steps in the procedure

        Example:
            get_procedure_chain("FIR")
            → ["FIR → Police_Investigation",
               "Police_Investigation → Chargesheet",
               "Chargesheet → Magistrate_Cognizance",
               "Magistrate_Cognizance → Trial",
               "Trial → Judgment"]
        """
        chain = []
        current = start_node

        # Follow "leads_to" and "triggers" edges
        FOLLOW_RELATIONS = {"leads_to", "triggers", "next_step"}

        visited = set()
        while current and current not in visited:
            visited.add(current)
            found_next = False
            for neighbor in self.G.successors(current):
                relation = self.G.edges[current, neighbor].get("relation", "")
                if relation in FOLLOW_RELATIONS:
                    chain.append(
                        f"{current.replace('_',' ')} → "
                        f"{neighbor.replace('_',' ')}"
                    )
                    current = neighbor
                    found_next = True
                    break
            if not found_next:
                break

        return chain


# ─────────────────────────────────────────────────────────────
# SINGLETON INSTANCE
# Built once at import time — reused for every query
# ─────────────────────────────────────────────────────────────

try:
    legal_graph = LegalKnowledgeGraph()
except Exception as e:
    print(f"[Graph] WARNING: Could not build knowledge graph: {e}")
    legal_graph = None


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("-" * 55)
    print("SaulGPT — Layer 6 Knowledge Graph Test")
    print("-" * 55)

    # Test 1 — Murder case
    print("\nTest 1: Murder query (IPC 302)")
    mock_results = [
        {"act_name": "IPC", "section_number": "302", "content": "..."}
    ]
    insights = legal_graph.expand_context(mock_results)
    for insight in insights:
        print(f"  {insight}")

    # Test 2 — FIR procedure chain
    print("\nTest 2: FIR Procedure Chain")
    chain = legal_graph.get_procedure_chain("FIR")
    for step in chain:
        print(f"  {step}")

    # Test 3 — CrPC arrest
    print("\nTest 3: CrPC arrest query")
    mock_results2 = [
        {"act_name": "CrPC", "section_number": "41", "content": "..."}
    ]
    insights2 = legal_graph.expand_context(mock_results2)
    for insight in insights2:
        print(f"  {insight}")

    print("\n" + "=" * 55)
    print("Layer 6 Knowledge Graph test complete.")
