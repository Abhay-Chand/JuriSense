/**
 * SAULGPT — LEGAL GLOSSARY
 * ===========================
 * 200+ Indian legal terms with plain-language definitions.
 * Used by the LegalTermsSidebar component.
 *
 * Structure: { term → { def, src, category } }
 */

export const GLOSSARY = {
  // ── CONSTITUTIONAL ───────────────────────────────────────────
  "article 14": { def: "Right to Equality — State shall not deny equality before law to any person.", src: "Constitution of India", category: "Constitutional" },
  "article 19": { def: "Right to Freedom — freedom of speech, expression, assembly, movement.", src: "Constitution of India", category: "Constitutional" },
  "article 21": { def: "Right to Life and Personal Liberty — no deprivation except by procedure established by law.", src: "Constitution of India", category: "Constitutional" },
  "article 21a": { def: "Right to Education — free and compulsory education for children 6–14 years.", src: "Constitution of India", category: "Constitutional" },
  "article 22": { def: "Protection against arbitrary arrest — right to be informed of grounds of arrest.", src: "Constitution of India", category: "Constitutional" },
  "article 23": { def: "Prohibition of forced labour, begar, and traffic in human beings.", src: "Constitution of India", category: "Constitutional" },
  "article 32": { def: "Right to Constitutional Remedies — move Supreme Court for enforcement of Fundamental Rights.", src: "Constitution of India", category: "Constitutional" },
  "article 226": { def: "Power of High Courts to issue writs for enforcement of rights.", src: "Constitution of India", category: "Constitutional" },
  "writ": { def: "A formal written order issued by a court — types: Habeas Corpus, Mandamus, Certiorari, Prohibition, Quo Warranto.", src: "Constitution of India", category: "Constitutional" },
  "habeas corpus": { def: "Writ requiring a person under arrest to be brought before a judge — protects against unlawful detention.", src: "Constitution", category: "Constitutional" },
  "mandamus": { def: "Writ commanding a public official or authority to perform a duty.", src: "Constitution", category: "Constitutional" },
  "certiorari": { def: "Writ to quash the order of an inferior court or tribunal.", src: "Constitution", category: "Constitutional" },
  "prohibition": { def: "Writ preventing an inferior court from exceeding its jurisdiction.", src: "Constitution", category: "Constitutional" },
  "quo warranto": { def: "Writ questioning the authority of a person holding public office.", src: "Constitution", category: "Constitutional" },
  "fundamental rights": { def: "Basic human rights guaranteed by the Constitution — enforceable by courts.", src: "Constitution Part III", category: "Constitutional" },
  "directive principles": { def: "Guidelines for government policy — not enforceable but fundamental in governance.", src: "Constitution Part IV", category: "Constitutional" },
  "fundamental duty": { def: "Moral obligations of citizens to promote patriotism and uphold Constitution.", src: "Constitution Part IV-A", category: "Constitutional" },
  "constitutional amendment": { def: "Change to the Constitution — requires special parliamentary procedure.", src: "Constitution Article 368", category: "Constitutional" },
  "judicial review": { def: "Power of courts to examine constitutionality of laws and executive actions.", src: "Constitution", category: "Constitutional" },
  "basic structure": { def: "Unalterable core of Constitution — cannot be destroyed by amendment.", src: "Kesavananda Bharati case", category: "Constitutional" },

  // ── BNS 2023 (replaced IPC 1860) ─────────────────────────────
  "bns": { def: "Bharatiya Nyaya Sanhita 2023 — replaced Indian Penal Code from July 1, 2024.", src: "BNS 2023", category: "Criminal Law" },
  "section 103 bns": { def: "Murder — punishment is death or imprisonment for life.", src: "BNS 2023", category: "Criminal Law" },
  "section 109 bns": { def: "Attempt to murder — punishment up to 10 years imprisonment.", src: "BNS 2023", category: "Criminal Law" },
  "section 115 bns": { def: "Voluntarily causing grievous hurt — up to 7 years imprisonment.", src: "BNS 2023", category: "Criminal Law" },
  "section 303 bns": { def: "Theft — punishment up to 3 years and fine.", src: "BNS 2023", category: "Criminal Law" },
  "section 318 bns": { def: "Cheating — punishment up to 3 years.", src: "BNS 2023", category: "Criminal Law" },
  "section 74 bns": { def: "Voluntarily causing hurt — up to 1 year imprisonment.", src: "BNS 2023", category: "Criminal Law" },
  "section 78 bns": { def: "Assault with intent to outrage modesty of a woman.", src: "BNS 2023", category: "Criminal Law" },
  "section 64 bns": { def: "Rape — minimum 10 years to life imprisonment.", src: "BNS 2023", category: "Criminal Law" },
  "section 106 bns": { def: "Causation of death by rash or negligent act.", src: "BNS 2023", category: "Criminal Law" },

  // ── IPC 1860 (repealed — historical reference) ───────────────
  "ipc": { def: "Indian Penal Code 1860 — REPEALED. Replaced by BNS 2023 from July 1, 2024.", src: "IPC 1860 [Repealed]", category: "Criminal Law" },
  "section 302": { def: "Murder under IPC (now § 103 BNS) — death or life imprisonment.", src: "IPC [Repealed]", category: "Criminal Law" },
  "section 304a": { def: "Causing death by negligence — applies to road accidents.", src: "IPC [Repealed]", category: "Criminal Law" },
  "section 307": { def: "Attempt to murder (now § 109 BNS).", src: "IPC [Repealed]", category: "Criminal Law" },
  "section 323": { def: "Voluntarily causing hurt — up to 1 year imprisonment.", src: "IPC [Repealed]", category: "Criminal Law" },
  "section 354": { def: "Assault with intent to outrage modesty of a woman.", src: "IPC [Repealed]", category: "Criminal Law" },
  "section 376": { def: "Rape — minimum 7 years to life imprisonment.", src: "IPC [Repealed]", category: "Criminal Law" },
  "section 406": { def: "Criminal breach of trust — up to 3 years.", src: "IPC [Repealed]", category: "Criminal Law" },
  "section 420": { def: "Cheating (now § 318 BNS) — up to 7 years.", src: "IPC [Repealed]", category: "Criminal Law" },
  "section 498a": { def: "Cruelty by husband or relatives of a woman.", src: "IPC [Repealed]", category: "Criminal Law" },
  "section 506": { def: "Criminal intimidation — threatening with injury.", src: "IPC [Repealed]", category: "Criminal Law" },

  // ── BNSS 2023 (replaced CrPC 1973) ───────────────────────────
  "bnss": { def: "Bharatiya Nagarik Suraksha Sanhita 2023 — replaced CrPC from July 1, 2024.", src: "BNSS 2023", category: "Criminal Procedure" },
  "crpc": { def: "Code of Criminal Procedure 1973 — REPEALED. Replaced by BNSS 2024.", src: "CrPC [Repealed]", category: "Criminal Procedure" },
  "fir": { def: "First Information Report — document recorded by police when cognizable offence reported. Mandatory first step in criminal complaints.", src: "BNSS 2023", category: "Criminal Procedure" },
  "chargesheet": { def: "Document filed by police in court after completing investigation — lists charges against accused.", src: "BNSS 2023", category: "Criminal Procedure" },
  "bail": { def: "Temporary release of an arrested person on condition they appear in court when required.", src: "BNSS 2023", category: "Criminal Procedure" },
  "anticipatory bail": { def: "Bail applied for before arrest — court may direct release if arrested.", src: "BNSS § 482", category: "Criminal Procedure" },
  "cognizable offence": { def: "Offence for which police can arrest without warrant — e.g. murder, theft, rape.", src: "BNSS 2023", category: "Criminal Procedure" },
  "non-cognizable": { def: "Offence where police cannot arrest without court warrant — e.g. cheating, defamation.", src: "BNSS 2023", category: "Criminal Procedure" },
  "remand": { def: "Court order sending accused into police or judicial custody for investigation or trial.", src: "BNSS 2023", category: "Criminal Procedure" },
  "section 161": { def: "Examination of witnesses by police during investigation.", src: "CrPC/BNSS", category: "Criminal Procedure" },
  "section 164": { def: "Recording confessions and statements before Magistrate.", src: "CrPC/BNSS", category: "Criminal Procedure" },
  "section 438": { def: "Anticipatory bail provision (now § 482 BNSS).", src: "CrPC [Repealed]", category: "Criminal Procedure" },
  "summons": { def: "Court order requiring a person to appear before it.", src: "BNSS 2023", category: "Criminal Procedure" },
  "warrant": { def: "Court order authorizing arrest or search.", src: "BNSS 2023", category: "Criminal Procedure" },
  "indictment": { def: "Formal accusation of a crime — charges framed by court.", src: "BNSS 2023", category: "Criminal Procedure" },
  "plea bargaining": { def: "Accused pleads guilty in exchange for lesser sentence.", src: "BNSS 2023", category: "Criminal Procedure" },

  // ── NEGOTIABLE INSTRUMENTS ACT ────────────────────────────────
  "section 138": { def: "Cheque dishonour — criminal liability for bounced cheque due to insufficient funds. Notice mandatory within 30 days.", src: "NIA 1881", category: "Commercial Law" },
  "section 141": { def: "Company officers (directors, managers) personally liable for cheque bounce offence.", src: "NIA 1881", category: "Commercial Law" },
  "nia": { def: "Negotiable Instruments Act 1881 — governs cheques, promissory notes, bills of exchange.", src: "NIA 1881", category: "Commercial Law" },
  "dishonour": { def: "Refusal by bank to pay a cheque — triggers legal rights under Section 138 NIA.", src: "NIA 1881", category: "Commercial Law" },
  "demand notice": { def: "Written notice within 30 days of cheque return demanding payment in 15 days — mandatory before filing NIA case.", src: "NIA § 138", category: "Commercial Law" },
  "promissory note": { def: "Written promise to pay a specified sum to a named person.", src: "NIA 1881", category: "Commercial Law" },
  "bill of exchange": { def: "Written order directing a person to pay a sum to another.", src: "NIA 1881", category: "Commercial Law" },
  "holder in due course": { def: "Person who acquires a negotiable instrument in good faith for value.", src: "NIA 1881", category: "Commercial Law" },
  "endorsement": { def: "Signing a negotiable instrument to transfer rights to another.", src: "NIA 1881", category: "Commercial Law" },

  // ── CIVIL PROCEDURE ───────────────────────────────────────────
  "cpc": { def: "Code of Civil Procedure 1908 — procedural law governing civil suits in India.", src: "CPC 1908", category: "Civil Procedure" },
  "plaint": { def: "Written statement filed by plaintiff initiating a civil suit.", src: "CPC 1908", category: "Civil Procedure" },
  "defendant": { def: "Party against whom a civil suit is filed.", src: "CPC 1908", category: "Civil Procedure" },
  "plaintiff": { def: "Party who initiates a civil suit.", src: "CPC 1908", category: "Civil Procedure" },
  "written statement": { def: "Defendant's formal reply to the plaint, admitting or denying each allegation.", src: "CPC 1908", category: "Civil Procedure" },
  "injunction": { def: "Court order restraining a party from doing something or compelling an action.", src: "CPC Order 39", category: "Civil Procedure" },
  "stay order": { def: "Court order temporarily stopping proceedings or execution of a lower court decree.", src: "CPC 1908", category: "Civil Procedure" },
  "ex parte": { def: "Proceedings conducted in absence of one party — can result in an ex parte decree.", src: "CPC 1908", category: "Civil Procedure" },
  "decree": { def: "Formal court decision on rights of parties — preliminary or final.", src: "CPC 1908", category: "Civil Procedure" },
  "execution": { def: "Enforcement of a court decree — attach property, arrest judgment debtor.", src: "CPC 1908", category: "Civil Procedure" },
  "attachment": { def: "Court seizure of property of judgment debtor to satisfy a decree.", src: "CPC 1908", category: "Civil Procedure" },
  "mesne profits": { def: "Profits received by person wrongfully in possession of property — recoverable by rightful owner.", src: "CPC 1908", category: "Civil Procedure" },
  "caveat": { def: "Notice filed asking court not to pass an order without hearing the caveator.", src: "CPC § 148A", category: "Civil Procedure" },
  "interlocutory order": { def: "Temporary court order made during pendency of suit — does not decide the final matter.", src: "CPC 1908", category: "Civil Procedure" },
  "specific performance": { def: "Court order compelling a party to perform their contractual obligation.", src: "Specific Relief Act 1963", category: "Civil Procedure" },
  "summary judgment": { def: "Judgment without full trial when no genuine dispute of fact exists.", src: "CPC Order 13A", category: "Civil Procedure" },
  "framing of issues": { def: "Court identifies disputed questions to be decided in the suit.", src: "CPC Order 14", category: "Civil Procedure" },
  "affidavit": { def: "Sworn written statement of facts — used as evidence in court proceedings.", src: "CPC / Evidence Act", category: "Civil Procedure" },

  // ── LIMITATION ACT ─────────────────────────────────────────────
  "limitation act": { def: "Limitation Act 1963 — prescribes time limits within which legal action must be filed.", src: "Limitation Act 1963", category: "Civil Procedure" },
  "time-barred": { def: "Claim filed after limitation period has expired — court will not entertain it.", src: "Limitation Act 1963", category: "Civil Procedure" },
  "limitation period": { def: "Maximum time allowed to file a legal action — typically 3 years for civil suits.", src: "Limitation Act 1963", category: "Civil Procedure" },
  "cause of action": { def: "The facts giving rise to a legal claim — limitation period begins from this date.", src: "Limitation Act 1963", category: "Civil Procedure" },
  "condonation of delay": { def: "Court's discretion to accept a case filed after limitation if 'sufficient cause' is shown.", src: "Limitation Act § 5", category: "Civil Procedure" },
  "acknowledgment": { def: "Written admission of liability — extends limitation period.", src: "Limitation Act § 18", category: "Civil Procedure" },

  // ── CONSUMER LAW ───────────────────────────────────────────────
  "consumer protection act": { def: "Consumer Protection Act 2019 — protects consumers from unfair trade, defects, deficiency in service.", src: "CPA 2019", category: "Consumer Law" },
  "deficiency in service": { def: "Shortcoming or inadequacy in the quality or nature of service promised.", src: "CPA 2019", category: "Consumer Law" },
  "unfair trade practice": { def: "Misleading advertisement, false claims, or deceptive business practices.", src: "CPA 2019", category: "Consumer Law" },
  "district commission": { def: "Consumer forum for claims up to ₹50 Lakhs.", src: "CPA 2019", category: "Consumer Law" },
  "state commission": { def: "Consumer forum for claims between ₹50 Lakhs and ₹2 Crores.", src: "CPA 2019", category: "Consumer Law" },
  "ncdrc": { def: "National Consumer Disputes Redressal Commission — claims above ₹2 Crores.", src: "CPA 2019", category: "Consumer Law" },
  "consumer": { def: "Person who buys goods or avails services for consideration.", src: "CPA 2019", category: "Consumer Law" },
  "complaint": { def: "Allegation in writing before a consumer forum — seeks relief under CPA.", src: "CPA 2019", category: "Consumer Law" },
  "product liability": { def: "Manufacturer or seller liable for harm caused by defective product.", src: "CPA 2019", category: "Consumer Law" },

  // ── LABOUR LAW ────────────────────────────────────────────────
  "retrenchment": { def: "Termination of employment by employer for reasons other than disciplinary action — compensation mandatory.", src: "Industrial Disputes Act 1947", category: "Labour Law" },
  "gratuity": { def: "Lump sum payment to employee on retirement or resignation after 5+ years of service.", src: "Payment of Gratuity Act 1972", category: "Labour Law" },
  "provident fund": { def: "Mandatory savings scheme where employer and employee contribute monthly — managed by EPFO.", src: "EPF Act 1952", category: "Labour Law" },
  "esic": { def: "Employees' State Insurance Corporation — provides medical and cash benefits to workers.", src: "ESI Act 1948", category: "Labour Law" },
  "notice pay": { def: "Payment in lieu of notice period when employment is terminated without notice.", src: "Shops & Establishments Act", category: "Labour Law" },
  "wrongful termination": { def: "Dismissal without following due process — employee entitled to reinstatement or compensation.", src: "Industrial Disputes Act", category: "Labour Law" },
  "industrial dispute": { def: "Dispute between employer and employees relating to employment terms.", src: "Industrial Disputes Act 1947", category: "Labour Law" },
  "layoff": { def: "Failure to continue employment due to circumstances beyond employer's control.", src: "Industrial Disputes Act 1947", category: "Labour Law" },
  "lockout": { def: "Temporary closing of business by employer during labour dispute.", src: "Industrial Disputes Act 1947", category: "Labour Law" },
  "minimum wages": { def: "Lowest wage payable by employer — fixed by government.", src: "Minimum Wages Act 1948", category: "Labour Law" },

  // ── PROPERTY LAW ──────────────────────────────────────────────
  "sale deed": { def: "Legal document that transfers ownership of immovable property from seller to buyer.", src: "Registration Act 1908", category: "Property Law" },
  "encumbrance": { def: "A claim or lien on property — mortgage, easement, or pending legal dispute.", src: "Transfer of Property Act", category: "Property Law" },
  "easement": { def: "Right of one person to use another's land for a specific purpose — e.g. right of way.", src: "Indian Easements Act 1882", category: "Property Law" },
  "partition": { def: "Division of jointly owned property among co-owners.", src: "Partition Act 1893", category: "Property Law" },
  "adverse possession": { def: "Acquiring title to property by continuous, open, and hostile possession for 12 years.", src: "Limitation Act", category: "Property Law" },
  "mortgage": { def: "Transfer of interest in property as security for payment of money lent.", src: "Transfer of Property Act", category: "Property Law" },
  "lease": { def: "Transfer of right to enjoy property for a specified time in exchange for rent.", src: "Transfer of Property Act", category: "Property Law" },
  "leave and licence": { def: "Permission to occupy property without creating tenancy rights — revocable by licensor.", src: "Indian Easements Act", category: "Property Law" },
  "title": { def: "Legal right to ownership of property.", src: "Property Law", category: "Property Law" },
  "conveyance": { def: "Transfer of property from one person to another.", src: "Transfer of Property Act", category: "Property Law" },
  "gift deed": { def: "Voluntary transfer of property without consideration.", src: "Transfer of Property Act", category: "Property Law" },
  "will": { def: "Legal document declaring how property shall be distributed after death.", src: "Succession Act", category: "Property Law" },

  // ── FAMILY LAW ────────────────────────────────────────────────
  "maintenance": { def: "Monthly payment ordered by court to support spouse or children after separation.", src: "CRPC § 125 / BNSS § 144", category: "Family Law" },
  "alimony": { def: "Financial support paid to spouse after divorce — permanent or interim.", src: "Hindu Marriage Act", category: "Family Law" },
  "custody": { def: "Legal right to care for and make decisions for a child — physical or legal custody.", src: "Guardians & Wards Act", category: "Family Law" },
  "dowry": { def: "Property or money given to groom's family by bride's family — giving/taking is illegal.", src: "Dowry Prohibition Act 1961", category: "Family Law" },
  "domestic violence": { def: "Physical, emotional, sexual, or economic abuse within a domestic relationship.", src: "PWDVA 2005", category: "Family Law" },
  "divorce": { def: "Legal dissolution of a marriage by court order.", src: "Hindu Marriage Act / Special Marriage Act", category: "Family Law" },
  "mutual consent divorce": { def: "Both spouses agree to end marriage — faster procedure, minimum 6 month waiting period.", src: "HMA § 13B", category: "Family Law" },
  "cruelty": { def: "Wilful conduct causing mental or physical suffering — ground for divorce.", src: "HMA § 498A", category: "Family Law" },
  "desertion": { def: "Abandonment of spouse without reasonable cause — ground for divorce.", src: "Hindu Marriage Act", category: "Family Law" },
  "guardianship": { def: "Legal authority over a minor's person or property.", src: "Guardians and Wards Act 1890", category: "Family Law" },
  "adoption": { def: "Legal process of taking a child as one's own.", src: "Hindu Adoption and Maintenance Act / Juvenile Justice Act", category: "Family Law" },
  "succession": { def: "Transfer of property after death — governed by personal law or Succession Act.", src: "Succession Act 1925", category: "Family Law" },

  // ── GENERAL LEGAL TERMS ────────────────────────────────────────
  "deponent": { def: "Person who makes an affidavit or gives sworn testimony.", src: "General", category: "General" },
  "perjury": { def: "Giving false evidence under oath — criminal offence punishable with imprisonment.", src: "BNS 2023", category: "General" },
  "contempt of court": { def: "Wilful disobedience of court order or conduct that disrespects court authority.", src: "Contempt of Courts Act 1971", category: "General" },
  "subpoena": { def: "Court summons requiring a person to appear or produce documents.", src: "CPC / BNSS", category: "General" },
  "arbitration": { def: "Alternative dispute resolution where parties agree to have dispute decided by arbitrator.", src: "Arbitration & Conciliation Act 1996", category: "General" },
  "mediation": { def: "Voluntary, confidential process where neutral mediator helps parties reach settlement.", src: "Mediation Act 2023", category: "General" },
  "lok adalat": { def: "People's Court — alternative forum for pre-litigation settlement. Award is final and binding.", src: "Legal Services Authorities Act", category: "General" },
  "legal notice": { def: "Formal written communication informing the recipient of legal action to be taken if grievance is not redressed.", src: "General Legal Practice", category: "General" },
  "power of attorney": { def: "Legal document authorizing one person to act on behalf of another.", src: "Powers of Attorney Act 1882", category: "General" },
  "indemnity": { def: "Agreement to compensate another party for loss or damage they may suffer.", src: "Indian Contract Act 1872", category: "General" },
  "liquidated damages": { def: "Pre-agreed amount payable on breach of contract — fixed in the contract itself.", src: "Indian Contract Act § 74", category: "General" },
  "tortfeasor": { def: "Person who commits a tort (civil wrong) causing injury or loss to another.", src: "Law of Torts", category: "General" },
  "vicarious liability": { def: "Legal responsibility of one person for torts committed by another — e.g. employer for employee.", src: "Law of Torts", category: "General" },
  "res judicata": { def: "Once a matter is decided by a competent court, same parties cannot litigate it again.", src: "CPC § 11", category: "General" },
  "sub judice": { def: "Matter currently under consideration by court — cannot be prejudged publicly.", src: "General", category: "General" },
  "prima facie": { def: "On first appearance — sufficient evidence to proceed unless rebutted.", src: "General Legal", category: "General" },
  "locus standi": { def: "Right or capacity to bring an action in court — must have sufficient connection to matter.", src: "General Legal", category: "General" },
  "amicus curiae": { def: "Friend of the court — person not party to case who assists court with information.", src: "General Legal", category: "General" },
  "suo motu": { def: "Court takes action on its own motion without any petition from parties.", src: "General Legal", category: "General" },
  "quantum": { def: "The amount or extent of damages — quantum of compensation to be awarded.", src: "General Legal", category: "General" },
  "mens rea": { def: "Criminal intent — guilty mind. Most offences require both act (actus reus) and intent.", src: "Criminal Law", category: "General" },
  "actus reus": { def: "The physical act constituting a crime — must be accompanied by mens rea for conviction.", src: "Criminal Law", category: "General" },
  "burden of proof": { def: "Obligation to prove facts in dispute — in civil cases on balance of probabilities, criminal beyond reasonable doubt.", src: "BSA 2023", category: "General" },
  "presumption": { def: "Assumption accepted as true unless contradicted by evidence.", src: "BSA 2023", category: "General" },
  "hearsay": { def: "Out-of-court statement offered as evidence — generally not admissible.", src: "BSA 2023", category: "General" },
  "bailable offence": { def: "Offence where bail is a right — accused can be released on bail.", src: "BNSS 2023", category: "General" },
  "non-bailable offence": { def: "Offence where bail is discretionary — court decides whether to grant.", src: "BNSS 2023", category: "General" },
  "compoundable offence": { def: "Offence where parties can settle — accused can be acquitted.", src: "BNSS 2023", category: "General" },
  "non-compoundable": { def: "Offence that cannot be settled — trial must conclude.", src: "BNSS 2023", category: "General" },
  "parole": { def: "Temporary release of prisoner for specific purpose.", src: "Prison Act 1894", category: "General" },
  "probation": { def: "Release of offender without imprisonment — subject to conditions.", src: "Probation of Offenders Act 1958", category: "General" },
  "defamation": { def: "Harming reputation by false statement — civil or criminal.", src: "BNS 2023", category: "General" },
  "libel": { def: "Defamation in written or permanent form.", src: "BNS 2023", category: "General" },
  "slander": { def: "Defamation in spoken or transient form.", src: "BNS 2023", category: "General" },
  "breach of contract": { def: "Failure to perform contractual obligations.", src: "Indian Contract Act 1872", category: "General" },
  "force majeure": { def: "Unforeseeable circumstances preventing contract performance.", src: "Indian Contract Act", category: "General" },
  "novation": { def: "Substitution of new contract for old one.", src: "Indian Contract Act", category: "General" },
  "guarantee": { def: "Contract to perform promise of another person if they default.", src: "Indian Contract Act", category: "General" },
  "bailee": { def: "Person to whom goods are delivered for safekeeping.", src: "Indian Contract Act", category: "General" },
  "bailor": { def: "Person who delivers goods to another for safekeeping.", src: "Indian Contract Act", category: "General" },
  "pledge": { def: "Bailment of goods as security for debt.", src: "Indian Contract Act", category: "General" },
  "agency": { def: "Relationship where one person acts on behalf of another.", src: "Indian Contract Act", category: "General" },
  "partnership": { def: "Association of persons sharing profits of business.", src: "Partnership Act 1932", category: "General" },
  "company": { def: "Legal entity separate from its members — incorporated under Companies Act.", src: "Companies Act 2013", category: "General" },
  "memorandum": { def: "Constitutional document of a company — defines scope of activities.", src: "Companies Act 2013", category: "General" },
  "articles of association": { def: "Rules governing internal management of a company.", src: "Companies Act 2013", category: "General" },
  "winding up": { def: "Process of dissolving a company.", src: "Companies Act 2013", category: "General" },
  "insolvency": { def: "Inability to pay debts when due.", src: "Insolvency and Bankruptcy Code 2016", category: "General" },
  "bankruptcy": { def: "Legal status of insolvent debtor.", src: "Insolvency and Bankruptcy Code 2016", category: "General" },
  "nclt": { def: "National Company Law Tribunal — adjudicates company law disputes.", src: "Companies Act 2013", category: "General" },
  "nclat": { def: "National Company Law Appellate Tribunal — hears appeals from NCLT.", src: "Companies Act 2013", category: "General" },
  "sebi": { def: "Securities and Exchange Board of India — regulates securities market.", src: "SEBI Act 1992", category: "General" },
  "rbi": { def: "Reserve Bank of India — central banking authority.", src: "RBI Act 1934", category: "General" },
  "rti": { def: "Right to Information — citizens' right to access government information.", src: "RTI Act 2005", category: "General" },
  "pil": { def: "Public Interest Litigation — litigation for public good.", src: "Constitution Article 32", category: "General" },
  "curative petition": { def: "Last judicial remedy after review petition — prevents miscarriage of justice.", src: "Supreme Court Rules", category: "General" },
  "review petition": { def: "Request to same court to review its judgment.", src: "CPC / Constitution", category: "General" },
  "special leave petition": { def: "Petition to Supreme Court for leave to appeal.", src: "Constitution Article 136", category: "General" },
  "transfer petition": { def: "Request to transfer case from one court to another.", src: "Constitution / CPC", category: "General" },
  "intervention": { def: "Third party joining ongoing litigation.", src: "CPC", category: "General" },
  "implead": { def: "Adding a necessary party to litigation.", src: "CPC Order 1", category: "General" },
  "necessary party": { def: "Party without whom no effective decree can be passed.", src: "CPC", category: "General" },
  "proper party": { def: "Party whose presence enables court to adjudicate effectively.", src: "CPC", category: "General" },
  "cause title": { def: "Heading of a legal document showing parties and court.", src: "General Legal", category: "General" },
  "cause list": { def: "List of cases scheduled for hearing.", src: "General Legal", category: "General" },
  "vacation bench": { def: "Special bench hearing urgent matters during court vacation.", src: "General Legal", category: "General" },
  "mentioning": { def: "Requesting early hearing of a matter.", src: "General Legal", category: "General" },
};

/**
 * Scan text and return all glossary terms found in it.
 * Returns array of {term, def, src, category} objects.
 */
export function scanForTerms(text) {
  if (!text) return [];
  const lower   = text.toLowerCase();
  const found   = [];
  const seen    = new Set();

  for (const [term, data] of Object.entries(GLOSSARY)) {
    if (lower.includes(term) && !seen.has(term)) {
      seen.add(term);
      found.push({ term, ...data });
    }
  }

  // Sort alphabetically
  return found.sort((a, b) => a.term.localeCompare(b.term));
}

/**
 * Get a single term definition.
 */
export function getTermDefinition(term) {
  const normalized = term.toLowerCase().trim();
  return GLOSSARY[normalized] || null;
}

/**
 * Get all terms in a category.
 */
export function getTermsByCategory(category) {
  const result = [];
  for (const [term, data] of Object.entries(GLOSSARY)) {
    if (data.category === category) {
      result.push({ term, ...data });
    }
  }
  return result.sort((a, b) => a.term.localeCompare(b.term));
}

/**
 * Get all unique categories.
 */
export function getCategories() {
  const categories = new Set();
  for (const data of Object.values(GLOSSARY)) {
    categories.add(data.category);
  }
  return Array.from(categories).sort();
}
