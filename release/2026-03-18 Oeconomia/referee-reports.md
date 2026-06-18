# Œconomia round-1 decision — referee reports

**Submission:** "History of climate finance as an economic object: accounting categories, controversies, and economists as policy experts" (Varia, submitted 2026-03-18).

**Decision received:** 2026-05-24, from Thomas Delcey (Managing Editor, `thomas.delcey@ube.fr`) on behalf of the Editor-in-Chief, via the journal platform (`journals.sfu.ca/oeconomia`).

**Outcome:** Not publishable in current form — **revise & resubmit, major revisions**. Resubmission via the "Revisions" form under the original submission; evaluated with the same care, acceptance not guaranteed. A response letter addressing each point is required.

**Reviewer recommendations:** Reviewer 1 — *Resubmit for Review*; Reviewer 2 — *Revisions Required*.

> Source: print-to-PDF of the editor's email, extracted with `pdftotext -layout`. Verbatim transcription below (ligature artifacts normalised; the editor's own spellings — "writting", "strenght", "subtantiated", "you own world" — preserved). Email header/footer and platform chrome omitted. The original PDF is not retained in the repository.

---

## Cover email

Dear Minh Ha Duong,

Thank you for submitting your paper "History of climate finance as an economic object: accounting categories, controversies, and economists as policy experts" to Œconomia – History / Methodology / Philosophy.

We have now received the reports on your paper. On the basis of the referees comments and of the editor's own reading of your paper, we consider that it is not publishable in its current form and we would like to encourage you to revise and resubmit your paper along the lines indicated by the comments below (at the end of this email).

The revisions called for are major ones, that is why we are asking you to resubmit your paper. The resubmission will be evaluated with the same care as the original submission, and ultimate acceptance is not guaranteed.

Please accompany any revision with a letter explaining how you have addressed the referees' and editor's points or why you have chosen not to do so.

To resubmit your paper you need to access our platform (http://journals.sfu.ca/oeconomia/index.php/oeconomia) using the same username and password as for the initial submission. You will be able to upload the revised version of your paper using the "Revisions" form, under your original submission.

If you have any questions, please contact me.

On behalf of the Editor-in-Chief,

Thomas Delcey
Managing Editor
Œconomia – History / Methodology / Philosophy
thomas.delcey@ube.fr

---

## Editor's decision

Both reviewers acknowledge the interest of the research object and the relevance of several analyses. I share this assessment. They also agree, and I fully concur, that the article currently falls short in its demonstration, on both substance and presentation.

Reviewer 2's remarks are particularly relevant regarding the writting: "sentences frequently define concepts by what they are not rather than by what they are, repeat high-level claims without advancing the analysis, and close paragraphs with broad declarative statements that remain analytically empty." This is not merely a stylistic issue, and it substantially undermines the article's analytical rigour. The number of strong but under-specified claims is too high to be listed here. The reviewers' comment will help the author identify them.

Reviewer 1's remark on the discussion of what is "economic thought" deserves a clarification in the introduction rather than a substantial revision. I think the references reviewer 1 mentions will help to clarify this point. At Oeconomia, we are particularly interested in the production of economic knowledge "in the grey literature", to use you own world.

Another central weakness I want to personally emphasize lies in the relationship between the historical analysis and the quantitative analysis, which remains particularly thin. The thesis is interesting, and the historical materials — contextualized word vectors and unsupervised learning — are well aligned with the state of the art in the history of economic thought. The quantitative analysis, however, falls well below the standards of the field. The article is transparent about the choices made but provides no justification for any of them. A non-exhaustive list of unanswered questions:

- How was the corpus constructed? Why these sources, documents, and reports?
- Why these three periods? How were they determined?
- Why co-citation analysis? Why limit it to 250 documents in Section 2?
- Why the Louvain algorithm rather than Leiden? Why a modularity of 0.68?
- What procedure was applied to clean the full texts?
- Why k-means? Why this number of clusters? Are robustness checks provided?

More fundamentally, as Reviewer 1 notes, the logical relationship between the historical narrative and the quantitative results remains unclear. Quantitative elements consistently appear after the historical account without any explicit framing of their role: are they confirmatory, exploratory, or generative? For instance, it is never established whether the three traditions presented in Section 1 are derived from Table 1 or the reverse. Similarly, Figure 2 is never mobilised in the argument of Section 1, which calls its function in the article into question.

For these reasons, I reject the article in its current form. Given our interest on the research agenda and methods, and the clear contribution potential identified by both reviewers, we strongly encourage the author to resubmit a substantially revised version. Such a revision requires, in my view, a much more direct, and likely, human engagement by the author with all of the points raised above.

Best,
Thomas Delcey

---

## Reviewer 1

The paper addresses a genuine gap in the historiography of climate economics. With substantial revisions, it could make a significant contribution to Œconomia. The three-act periodisation is convincing, and the central thesis that climate finance became governable through the deliberate ambiguity of its accounting categories, rather than despite it, is an original and thoughtful claim. The distinction between commensuration (rendering things comparable) and economisation (rendering them amenable to financial reasoning) is the paper's most promising analytical contribution, which can be further developed.

However, the paper suffers from a persistent gap between the intellectual-history claim announced in the introduction and the institutional history actually delivered. The manuscript promises an analysis of how economists constructed climate finance as an economic object, but the evidence points primarily to policy professionals in international organisations. Additionally, the computational analysis, while commendable in scope, remains weakly connected to the historical argument. Finally, several important dimensions of the climate finance landscape — the insurance/loss-and-damage logic, the connection to the broader finance-development literature, the role of non-economist actors — are insufficiently addressed. Please find my comments below:

### 1. The central claim about "economists" is under-specified

The paper repeatedly attributes the construction of climate finance to "economists" (e.g., "it was economists in international organisations who built the measurement instruments," p. 17). But the key figures named — Jan Corfee-Morlot at the OECD, Raphaël Jachnik and Roberta Caruso in the Research Collaborative, the DAC statisticians who designed Rio markers — are policy professionals, not academic economists. The paper conflates two distinct corpora and two distinct forms of epistemic authority: (a) academic development economics as a theoretical discipline (Easterly, Rodrik, Banerjee, etc.), and (b) the statistical and accounting apparatus produced by OECD-DAC practitioners working within institutional mandates. The fact that these practitioners were trained as economists does not make their output "economic thought" in the sense that Œconomia's readership would expect.

This conflation weakens the paper's own argument. If the authors mean that economic categories and reasoning styles — cost-benefit logic, efficiency criteria, market-failure frameworks — shaped how climate finance was made calculable, then the argument should be framed as one about the diffusion of economic rationality into institutional practice. Alternatively, if the claim is genuinely about the role of individual economists, the paper needs much more evidence about the intellectual resources these individuals mobilised and the theoretical debates they responded to.

This point is reinforced by the paper's own corpus analysis: Table 2 shows that the core publication venues are climate governance and energy policy journals (Climate Policy, Climatic Change, Energy Economics), not economics journals. No AER, QJE, JPE, Econometrica, or even JEEM appears among the venues of highly cited works. If climate finance was constructed primarily by economists, one would expect at least some imprint in the economics literature. The paper should address this absence explicitly and reflect on what it means for the "history-of-economic-thought" framing.

An additional suggestion: the reference to Golka (2024), "Epistemic Gerrymandering: ESG, Impact Investing, and the Financial Governance of Sustainability" (Review of International Political Economy, 31:6, 1894–1918), would be useful here. Golka demonstrates that epistemic authority in sustainable finance is exercised through a productive circularity involving financial institutions, not solely economists. The category-making was carried out by a broader set of actors, including development banks, multilateral secretariats, and financial practitioners.

### 2. Computational analysis

The authors are cautious about their computational analysis, acknowledging that it "corroborates" rather than generates the historical narrative (p. 4–5). Nevertheless, the corpus analysis occupies substantial space (corpus evidence subsections in each act, two figures, two tables) without delivering commensurate analytical returns. The periodisation stands or falls on the historical argument alone; the corpus confirms that publication volume increased after Copenhagen and that vocabulary shifted, but these are unsurprising findings that could be established by simpler bibliometric means.

Also, the corpus evidence occasionally diverges from the narrative, a divergence the paper acknowledges but does not fully resolve. The most striking case is the burden-sharing tradition (§1.3): the paper anchors it in Negishi (1960) and welfare-theoretic reasoning, but the co-citation analysis reveals that the actual pre-2007 community was anchored by North (1990), DiMaggio and Powell (1983), and Finnemore and Sikkink (1998). This divergence between the intellectual-history narrative and the citation practice it claims to track deserves more reflection. Was the burden-sharing tradition less important than the paper suggests?

### 3. Commensuration and economisation

The distinction between commensuration (Espeland and Stevens, 1998) and economization (Çalışkan and Callon, 2009) is a strenght of the paper. "commensuration makes things comparable; economization makes them amenable to financial reasoning — cost-benefit assessment, leverage calculation, de-risking ratios — thereby constituting the climate problem as economic and foreclosing framings centred on reparative justice or ecological debt" (p. 14). However, the paper deploys it once in Section 2 and then drops it. The distinction should structure the analysis throughout — showing at each stage how a commensuration move (the creation of Rio markers as tracking tools) became an economisation move (their use to calculate leverage ratios and claim compliance with the $100 billion target).

### 4. Loss and damage, and the insurance logic

The paper argues that post-2015 disputes operate "within the categories established during crystallisation." This is largely true for the $100 billion accounting battles, but the emergence of loss-and-damage financing (Warsaw International Mechanism, 2013; Santiago Network, 2022; Loss and Damage Fund, 2023) introduces a genuinely different logic that does not fit neatly within the crystallisation-era categories. Loss-and-damage financing rests on an actuarial/insurance logic — compensation for climate impacts based on prospective risk, not on differential historical responsibility (burden-sharing) or efficiency of allocation (market-failure framework). It is closer to a liability regime than to either the incremental-cost framework of Article 4.3 or the mobilisation framework of post-Copenhagen accounting. The authors should acknowledge this as a challenge to the claim that the post-2015 period operates entirely within established categories. The topic cannot be ignored in a paper that claims to cover climate finance through 2024.

A related theoretical opening: the insurance framing connects with game-theoretic and coalition-formation models of international environmental agreements. The shift from burden-sharing to insurance implies different coalition structures and different conditions for cooperation. This dimension, briefly noted in the burden-sharing section (§1.3), could be developed.

**Additional question: connection with the finance-development nexus literature**

A question remains about the absence of a connection between climate finance and the economic literature on the relationship between financial systems and economic development. The finance-development nexus — from King and Levine (1993) through Aghion and Bolton to contemporary work on financial deepening in developing economies — is directly relevant to understanding why climate finance was framed in terms of "mobilisation," "leverage," and "crowding-in" of private capital. The paper's account of the crystallisation period would benefit substantially from situating the vocabulary of "blended finance" and "de-risking" within this intellectual lineage. Also, the fact that climate finance developed as a largely self-contained accounting category, disconnected from these debates, deserves analysis.

**Other comments:**

- **P. 3:** "A new kind of economic object: one that required not just models but accounting infrastructure" — the opposition between models and accounting infrastructure is presented as self-evident, but it is not. The distinction the authors seem to have in mind is between theoretical modelling (IAMs) and statistical measurement (DAC reporting), which is not the same as models vs accounting. Need to be clarified.
- **P. 3:** "Rather than treating climate finance as a technical extension of environmental or development economics, we situate it within a longer trajectory of climate economics" — the intention behind this claim needs clarification.
- The paper should more explicitly justify the corpus boundaries, particularly the inclusion criteria for grey literature and the exclusion criteria for institutional documents. Given that economics journals are underrepresented in the corpus, the paper should address whether this reflects the field's actual disciplinary composition or a selection effect of the sources used (OpenAlex, ISTEX, OECD/WB/UNFCCC reports).
- The paper states that the $100 billion was "not derived from any economic model or needs assessment" (p. 12) but emerged from diplomatic bargaining. This is an important claim that could be documented more precisely.

**Recommendation: Resubmit for Review**

---

## Reviewer 2

**General comments:**

The manuscript's intellectual-historical approach to climate finance concepts and accounting mechanisms is promising, particularly in linking conceptual genealogy to institutional translation in climate governance. One of the manuscript's central claims—that the categories that made climate finance measurable also made it politically contestable because their translation from qualitative realities into quantitative indicators was inherently indeterminate—is potentially innovative and should be more explicitly substantiated throughout the paper. The overall argument would also benefit from greater analytical concreteness regarding the actual sites, actors, and institutional mechanisms of climate finance: who is involved, through what instruments, and in what markets or reporting systems these processes take place. I am not fully convinced by the chronological structure, given the relatively short period covered. In several places, the argument seems to be driven less by temporal sequence than by specific institutional ruptures or key political decisions; structuring the paper more around such turning points might strengthen the analysis.

The manuscript would also benefit from a more direct authorial engagement with its own argument and prose. In several places, the writing relies on formulaic, abstract, or repetitive formulations that resemble generic AI-generated academic language: sentences often define what a concept is not rather than specifying what it is, repeat high-level claims without advancing the analysis, or conclude paragraphs with broad declarative statements that remain analytically empty. When analytical tasks are outsourced to generic automated phrasing, the result is often verbosity and abstraction in place of demonstration, which creates an additional burden for the reader and reviewer. I strongly encourage the author to revise the manuscript in a more direct, concrete, and substantively engaged prose, ensuring that each sentence advances a concrete argument subtantiated by concrete examples and supported by primary or secondary sources.

**Linear comments:**

- What are the Rio markers (you partially define them on p. 8, but this is not their first occurrence). Please define them at first mention.
- In general try to reduce the use of jargon. For example (p. 7): "This system embodied specific conceptual commitments: the distinction between "concessional" and "non-concessional" flows, the requirement that ODA have a "grant element" of at least 25%, the counting of face value rather than subsidy content": There is a lot to unpack here (concessional vs non-concessional flows, grant element, face value vs subsidy content). Please explain these terms concretely.
- In the Development economics section, can you document more explicitly how economic reasoning translated into international negotiations here? What actors, institutions, or mechanisms carried this reasoning into the negotiation process?
- Avoid abstract formulations such as "These were not natural categories but historical constructs." Please state the substantive claim directly and concretely.
- You define the Development Assistance Committee (DAC) on p. 13, but refer to it several times from p. 7 onward. Please define it at first occurrence.
- p. 7 You quote Desrosières here, but the quotation is not sufficiently connected to the empirical case. Please explain concretely how this insight applies in this instance.
- Who were the development economists involved in the OECD case? Naming actors here would strengthen the argument.
- What is the GNI target? Please define it for readers unfamiliar with the term.
- You argue that climate policy borrowed the development aid reporting system, but it is not clear why this is analytically or politically problematic. Please explain the consequences more explicitly, and specify who drove this borrowing and how.
- I do not follow this sentence ("Article 4.3… encoded the burden-sharing principle in transactional language…"). How aggregate financial flows are not part of a transactional language? What is the argument here? Why would it have been important to connect the burden-sharing principle with financial flows? Is the most crucial question here "how do we count what has been paid?"
- Can you describe the "rigorous incremental-cost framework" more concretely?
- p. 8 How do we know that "the need for a broader category arose"? Please provide evidence or examples.
- Please date and explain more clearly when the incremental-cost framework was abandoned rather than extended, and why.
- p. 8 Can you explain how, why and with what consequences "The economic models that informed the negotiations treated transfers between regions as welfare-theoretic constructs, not as real-world financial flows requiring institutional tracking."?
- Can you explain more concretely how the Clean Development Mechanism functioned in practice?
- p.9 This claim ("the concept later migrated…") needs to be developed and illustrated with examples.
- Can you substantiate the claim that "the CDM produced a vocabulary of carbon accounting, not financial accounting"? What is the distinction in practice?
- p.9 "Moreover, the CDM's collapse after 2012—when CER prices fell below €1 as demand evaporated—demonstrated the fragility of market-based transfer mechanisms and reinforced the demand for a more rigorous, budget-based accounting of climate finance.": Who generated this demand? Which actors are involved here? Please specify.
- What is the Bali Action Plan? Please explain what changed institutionally and politically between Article 4.3 and Decision 1/CP.13, and what triggered that shift.
- p. 12 You introduce "political legitimacy" here rather suddenly. Why does this become a concern at this stage, and for whom?
- The claim that a bureaucratic decision (UNFCCC 2007) and a publication (the Stern Review) "created the conditions for a new kind of economic object" is so strong as currently stated that it needs to be demonstrated more carefully.
- The sentence "an economic object… that required not just models but accounting infrastructure" remains too abstract. Please specify concretely what you mean.
- What happened in Copenhagen? This discussion needs more historical context and explanation of why the $100bn commitment emerged. Moreover, such an amount of money seems anecdotal. By comparison, the US national defense asked the Congress to grant them $1.5 trillion for 2027 alone for example.
- Can you explain more clearly what you mean by the Barnesian form here?
- What are GEF grants? Please define.
- How did climate finance become politically binding? Through which institutional or legal mechanisms?
- p. 12 The claim about measurement apparatus and performativity needs to be unpacked much more concretely: what apparatus, what methodologies, and what practical consequences?
- In general in the article, the performativity argument feels more declarative than explanatory. Please clarify what analytical work it is doing here.
- p. 13 The role and functioning of Rio markers needs much more explanation: in what reporting context are they used, by whom, and for what purpose?
- I am not convinced that Desrosières and Porter are the most appropriate references for your claim about biased architectures of aid. You may want to engage more directly with critical scholarship on development aid (e.g. Arturo Escobar, Tim Mitchell).
- When discussing UNFCCC reporting practices, please clarify: to whom are these flows reported, by whom, and for what institutional purpose?
- Please describe the competing measurement regimes between donors and recipient countries more explicitly and explain how donors and recipients use them differently.
- Several concluding sentences remain formulaic and repetitive (e.g. "The vocabulary was not descriptively neutral…"). Please state the substantive analytical point more directly. What is the "particular vision" you are referring to?
- Section 2.3 in general would benefit from substantially more examples and primary and/or secondary sources supporting specific claims.
- p. 15 The claim about OECD expert groups developing standardized methodologies "that effectively set the terms of debate" is too vague as currently written. Please specify when, where, which experts, what methodologies, and what debates are being referred to.
- Can you provide concrete examples to substantiate the claim about the crystallization of an accountability vocabulary?
- p. 16 It may also be analytically interesting to reflect on the composition of the UN Advisory Group on Climate Change Financing (finance ministers, economists, central bankers, but no climate scientists). Does this institutional composition matter for your argument?

**Recommendation: Revisions Required**
