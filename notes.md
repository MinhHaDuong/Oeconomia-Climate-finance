# Notes for the Oeconomia draft

## Proposed title:

How Climate Finance Became an Economic Object: The Making of OECD/UNFCCC Categories and the Stabilization of a Field (1990-2025)

## Initial suggestion by ChatGPT

1) « Comment la finance climat est devenue un objet économique (1992-2022) » : une historiographie des catégories OCDE/UNFCCC

Angle : Comment les catégories techniques (dons, prêts, finance mobilisée, bilatéral/multilatéral) ont été stabilisées entre Rio, Kyoto, Paris, Glasgow. Essentiellement : l’histoire invisible d’une comptabilité devenue performative.

Pourquoi c’est bon pour Œconomia :
Le CfP insiste sur analytical issues, history of instruments, prehistory of the field. Tu peux raconter une histoire institutionnelle + politique + métrologique.

Apport pour ton livre : chapitre “Selon l’OCDE, les 100 milliards y sont / un résultat contesté” → tu transformes un chapitre en article académique.

Donne accès à ta valeur ajoutée : tu as toutes les archives OCDE, UNFCCC, Oxfam, SCF, et tu sais lire les bascules de définition (ex : “mobilised private finance”).

## Editorial requirements

- Language ?
- Length ?
- Format ?
- la dimension 'histoire des idées' et la place des économistes soient bien mises en évidence.

## Proposed framing by Claude

To examine:

- How economists shaped the definitions and measurement frameworks that made climate finance countable and governable
- The intellectual genealogy connecting development economics, environmental economics, and climate policy
- Key controversies (OECD vs. Oxfam methodologies, additionality debates, public vs. private finance)
- How these categorizations influenced the $100 billion commitment and its successor negotiations

The idea is to reuse the contents for my book on "How to spend $300 billions while meeting the journal's requirement for strong "history of economic ideas" content.

## Provisional definition: What is "climate finance" ?

Climate finance refers to the financial resources—local, national, or transnational—mobilized to help mitigate and adapt to climate change. It encompasses funding from public, private, and alternative sources that supports actions to reduce greenhouse gas emissions (mitigation) or help communities and ecosystems cope with climate impacts (adaptation).

The term covers several dimensions:

- Sources of funding include government budgets, development banks, multilateral climate funds (like the Green Climate Fund), private investment, and increasingly innovative mechanisms such as green bonds or carbon market revenues.

- Uses range from renewable energy deployment and energy efficiency improvements to climate-resilient infrastructure, early warning systems, sustainable agriculture, and ecosystem protection.

= A key political dimension involves the commitment made by developed countries under the UNFCCC framework to mobilize $100 billion annually by 2020 to support climate action in developing countries—a target that became a major point of contention in international negotiations, as accounting methodologies and actual delivery have been disputed.

The field has grown substantially as climate policy has matured, with debates now centering on how to scale up private finance, ensure funds reach the most vulnerable populations, and balance mitigation and adaptation spending.

## Data

- I have a corpus of 484 articles with "Climate finance" OR "Finance climat" OR "Finance climatique" from search.istex. avec texte intégral PDF et nettoyé
- A compléter avec BIBCNRS (FRANCIS)
- A compléter avec ...

## Méthodes


**1. Construire un corpus “Climate Finance” solide et exploitable (RAG)**

Je vais :

* Partir de mes **484 articles ISTEX “Climate Finance”** identifiés.
* Étendre avec des outils qui minent Web of Science, JSTOR, EconLit.
* Étendre le corpus aux revues et rapports du Sud (atténuer le biais OCDE).
* Étendre le corpus aux rapports institutionnels (BM, FMI, OCDE, UNFCCC, IPCC, AFD, ODI…).
* Uniformiser tout le corpus en TEI → JSONL → index vectoriel.
* Monter un **RAG scientifique** pour analyser :

  * la généalogie de la finance carbone (MDP → Article 6 → VCM),
  * les concepts “flexibilité temporelle/spatiale”,
  * les discours d’investissement climat dans les pays en développement.

But : préparer des analyses interactives solides pour mon projet d’article Oeconomia.

**2. Finetuning d’un modèle 7B sur “Tout Oeconomia”**

Objectif : obtenir un modèle spécialisé **capable d’écrire comme Oeconomia**, pour analyser style, arguments, catégories disciplinaires.

Je vais :

* Récupérer les **598 articles Oeconomia dans ISTEX**.
* Construire un corpus complet “Tout Oeconomia”.
* Ajouter une centaine d'articles du corpus précédent (échantillon stratifié par période) pour les concepts et la phraséologie de la finance climat.
* Finetuner un modèle 7B (Llama 3.2 / Mistral NeMo 7B / modèle open HNLab) sur le **style** (pas sur les faits).
* Tester génération, résumé, classification d’arguments, repérage de filiations intellectuelles.

## Messages clés

## Figures et tables

## Proposition Plan Article

# Proposition d'angle ChatGPT

How Climate Finance Became an Economic Object (1990–2025)
The Making of OECD/UNFCCC Categories and the Stabilization of a Field

## 1) L’ANGLE : ce que tu veux vraiment démontrer

Ton article doit montrer que “la finance climat” n’est pas tombée du ciel :
c’est un objet construit par :

des économistes du développement,

des fiscalistes du climat,

des statisticiens de l’OCDE,

des policy-analysts des COP,

des think tanks (WRI, CPI),

des acteurs diplomatiques.

Donc : un objet métrologique (au sens de Desrosières + Fourcade + Porter) devenu gouvernable grâce à des catégories économiques stabilisées entre 1990 et 2025.

## Pour Œconomia, c’est parfait, car c’est :

histoire de la pensée économique

histoire de la quantification

histoire institutionnelle

économie du développement + économie de l’environnement

## 2) LA THÈSE (claire, publishable)

Climate finance became an “economic object” once specific economists and institutions succeeded in stabilizing categories that made it measurable, comparable, and therefore governable. Between 1990 and 2025, OECD/DAC, UNFCCC bodies, and epistemic communities progressively co-produced a taxonomy—grants, concessionality, mobilized private finance, additionality—that turned an ambiguous diplomatic promise into a quantifiable field.

## 3) LA STRUCTURE DE L’ARTICLE (proposition sérieuse pour Œconomia)

### I. Origins: Before Climate Finance Was a Thing (1990–2005)

Contexte post-Rio : environnement = “externalité” → traité via aid, pas via finance.

Influence de l’économie du développement : catégories DAC, notion de concessionality, grant-equivalent.

L’économie de l’environnement domine les COP : JI, MDP → infrastructures conceptuelles.

Pourquoi la finance climatique n’existe pas encore comme objet autonome.

Historiographie : Desrosières (commensuration), Porter (Trust in Numbers), Fourcade (économistes transnationaux), Mahoney/Thelen (gradual change).

### II. The Shift: Defining Climate Finance (2009–2015)

(Copenhague → Paris)

Le “$100 billion” comme promesse performative (Callon, MacKenzie).

La bataille OCDE vs. UNFCCC pour la définition opérationnelle.

Les économistes du climat (Banque Mondiale, WRI, CPI, OCDE EPOC) et leur rôle.

Construction de la Rio Marker methodology → catégorisation climatique au sein de l’aide.

Apparition des concepts :

public climate finance

private finance mobilisée

crowding-in

leverage ratios

→ Stabilisation précaire des instruments.

### III. Metrisation and Contestation (2015–2021)

Paris Agreement : importance des transparency frameworks.

Comment le SCF (Standing Committee on Finance) produit un contre-savoir face à l’OCDE.

Oxfam, CARE, Third World Network remettent en cause la méthodologie (grant-equivalent vs face value).

Débat sur l’additionalité, le double-counting, les prêts non-concessionnels.

Rôle des économistes du GCF, GEF, MDBs : leurs modèles de leverage, leurs matrices de risques.

La finance climat devient un champ professionnalisé, avec ses métriques, ses institutions, ses carrières, ses routines statistiques.

### IV. The 2021–2025 Moment: The Closure of a Field

Glasgow : “the $100bn will be met in 2023” → comment l’affirmation repose sur une infrastructure statistique.

OCDE publie les chiffres validant l’objectif ; contestation du Sud global.

La notion de “climate finance architecture” devient dominante.

Vers le “new collective quantified goal” (NCQG) → montée en puissance des économistes dans le processus.

Les catégories DAC deviennent le langage officiel du climat, malgré leur origine développementiste.

### V. Argument central : How Finance Became an Economic Object

Ici, tu fais la démonstration théorique requise pour Œconomia :

Commensuration (Desrosières) : rendre mesurable ce qui ne l’était pas.

Performativité (Callon, MacKenzie) : les métriques produisent la réalité qu’elles mesurent.

Économisation (Fourcade, Çalışkan) : transformation d’un problème politique en problème économique.

Boundary-work : comment les économistes se sont imposés face aux juristes, aux diplomates, aux climatologues.

Infrastructures cognitives : tables DAC, logic models des MDBs, methodologies UNFCCC biennial reports.

Tu montres que la finance climat est devenue un objet gouvernable parce qu’elle est devenue un objet économique.

### VI. Conclusion : Implications pour le NCQG et pour la politique climatique mondiale

Sans stabilisation des catégories, aucun financement massif n’est gouvernable.

Le passage de 100 à 300 milliards dépend d’outils économiques préexistants.

La rhétorique sur les montants cache la bataille réelle sur la définition de ce qui “compte”.

Ce que signifie la domination des économistes dans la future architecture financière (GCF 2.0, Loss & Damage Fund, MDB reforms).
