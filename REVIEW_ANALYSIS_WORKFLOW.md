\# BasketBridge — Review Analysis Workflow



\## What this demonstrates



This repository contains the review-analysis workflow used to generate the quantitative research evidence for the BasketBridge product case study.



The workflow transforms multi-source public reviews and discussions into structured product-discovery signals that can be analyzed for recurring barriers, discovery methods, pain points, user needs, and product themes.



This is an independent case-study analysis. It does not use Blinkit internal customer or transaction data.



\---



\## Workflow



```text

PUBLIC REVIEWS \& DISCUSSIONS

Reddit · YouTube · App Store · Play Store · Trustpilot

&#x20;               ↓

&#x20;       CLEAN + NORMALIZE

&#x20;               ↓

&#x20;      RELEVANCE FILTERING

&#x20;               ↓

&#x20;      2,293 RELEVANT REVIEWS

&#x20;               ↓

&#x20;GEMINI STRUCTURED INSIGHT EXTRACTION

&#x20;               ↓

&#x20;  ┌────────────────────────────┐

&#x20;  │ 2,233 structured insights │

&#x20;  │ 60 failed extractions     │

&#x20;  └────────────────────────────┘

&#x20;               ↓

&#x20;    VALIDATION + QUALITY CHECKS

&#x20;               ↓

&#x20;      AGGREGATE ANALYSIS

&#x20;               ↓

&#x20;Barriers · Discovery Methods ·

&#x20;Pain Points · Needs · Categories

&#x20;               ↓

&#x20;      PRODUCT SYNTHESIS

1. Multi-source collection



Public reviews and discussions were collected from multiple sources rather than treating a single platform as representative of all shoppers.



Among the 2,293 reviews retained as relevant:



Source	Relevant reviews	Share

Reddit	1,369	59.7%

YouTube	576	25.1%

App Store	186	8.1%

Play Store	157	6.8%

Trustpilot	5	0.2%

Total	2,293	100%



Raw source data is available under data/raw/.



Cleaning and normalization logic is implemented in analysis/clean\_reviews.py and related pipeline scripts.

2. Relevance filtering



The collected material contains discussion that is not useful for the product-discovery research question.



The relevance stage separates useful material from irrelevant content before structured insight extraction.



Output: 2,293 relevant reviews



Inspect the retained dataset:



data/cleaned/relevant\_reviews.csv



Inspect excluded material:



data/cleaned/irrelevant\_reviews.csv



Implementation:



analysis/filter\_relevant\_reviews.py

3. Gemini-powered structured insight extraction



Each relevant review is transformed into structured fields that can be aggregated rather than relying only on manual reading of thousands of unstructured comments.



The extraction pipeline produces signals including product-discovery and exploration attributes used in the downstream analysis.



Input: 2,293 relevant reviews



Successfully structured: 2,233



Failed extraction: 60



Therefore failed records are retained separately rather than silently treated as successful classifications.



Implementation:



analysis/extract\_review\_insights.py



Structured output:



data/processed/review\_insights.csv



Failed records:



data/processed/failed\_reviews.csv

4. Unknowns and denominator discipline



Not every review contains evidence for every research field.



Among the 2,233 structured insights:



778 had no identifiable exploration barrier.

1,868 had no identifiable discovery method.

881 had no identifiable product category.



These records are not forced into unsupported classifications.



When percentages exclude Unknown, the denominator is only the subset where that signal was identifiable.



For example:



Exploration barriers



1,455 reviews contained an identifiable barrier.
Barrier	Count	% of identifiable barriers

Price Concern	426	29.3%

Trust	409	28.1%

Lack of Awareness	173	11.9%

App Experience	159	10.9%

Habit	149	10.2%

Limited Information	114	7.8%

No Need	24	1.6%

Poor Recommendations	1	0.1%



Discovery methods



365 reviews contained an identifiable discovery method.



Method	Count	% of identifiable methods

Search	114	31.2%

Categories	86	23.6%

Offers	83	22.7%

Homepage	42	11.5%

Recommendations	21	5.8%

Previous Orders	19	5.2%



These percentages describe the analyzed review subsets. They should not be interpreted as percentages of Blinkit customers.

5. Aggregate analysis



The structured dataset is aggregated to identify recurring patterns including:



exploration barriers

discovery methods

sentiment

pain-point themes

user-need themes

product features

categories mentioned



The generated analysis is available here:



reports/discovery\_report.md



Report generation:



analysis/generate\_report.py



Additional quality-analysis code:



analysis/data\_quality.py

6. From research evidence to product decisions



The workflow is designed to support product reasoning rather than automatically turn review frequencies into product decisions.



Two examples from the quantitative evidence:



Price Concern (29.3%) + Trust (28.1%) were the largest identifiable exploration barriers



→ New-category discovery should carry confidence information such as price, discount, ratings, or contextual relevance rather than presenting an unfamiliar product without support.



Search (31.2%) was the most common identifiable discovery method, while Recommendations represented 5.8%



→ The product hypothesis became: introduce discovery inside an existing shopping mission rather than requiring the shopper to adopt a separate browsing behavior.



These findings were subsequently combined with primary research and product reasoning in the case study. The review-analysis percentages alone are not treated as population-level customer behavior.

Reproduce / inspect the workflow



Key implementation files:



analysis/clean\_reviews.py — cleaning

analysis/merge\_reviews.py — source merging

analysis/filter\_relevant\_reviews.py — relevance filtering

analysis/extract\_review\_insights.py — Gemini structured extraction

analysis/data\_quality.py — quality checks

analysis/generate\_report.py — aggregate report generation



Key evidence outputs:



data/cleaned/relevant\_reviews.csv

data/processed/review\_insights.csv

data/processed/failed\_reviews.csv

reports/discovery\_report.md

Important evidence boundary



This workflow analyzes public reviews and discussions for an independent product-management case study.



It does not represent:



Blinkit internal analytics

Blinkit customer-level behavioral data

population estimates of Blinkit customers

production recommendation-system performance

completed A/B-test results



The quantitative outputs are research signals used alongside primary research and product judgment.

