# Blinkit AI-Powered Discovery Engine Report

## 1. Dataset Overview

- Reviews with extracted insights: **2,233**
- Reviews without an identifiable exploration barrier: **778 (34.8%)**
- Reviews without an identifiable discovery method: **1,868 (83.7%)**
- Reviews without an identifiable product category: **881 (39.5%)**

Percentages in sections that exclude `Unknown` are calculated only among reviews where that signal could be identified.

## 2. Sentiment Distribution

| sentiment   |   Count |   Percentage |
|:------------|--------:|-------------:|
| Negative    |     864 |         38.7 |
| Neutral     |     666 |         29.8 |
| Positive    |     607 |         27.2 |
| Mixed       |      96 |          4.3 |

## 3. Category Exploration Barriers

| exploration_barrier   |   Count |   Percentage |
|:----------------------|--------:|-------------:|
| Price Concern         |     426 |         29.3 |
| Trust                 |     409 |         28.1 |
| Lack of Awareness     |     173 |         11.9 |
| App Experience        |     159 |         10.9 |
| Habit                 |     149 |         10.2 |
| Limited Information   |     114 |          7.8 |
| No Need               |      24 |          1.6 |
| Poor Recommendations  |       1 |          0.1 |

## 4. Product Discovery Methods

| discovery_method   |   Count |   Percentage |
|:-------------------|--------:|-------------:|
| Search             |     114 |         31.2 |
| Categories         |      86 |         23.6 |
| Offers             |      83 |         22.7 |
| Homepage           |      42 |         11.5 |
| Recommendations    |      21 |          5.8 |
| Previous Orders    |      19 |          5.2 |

## 5. Recurring Pain-Point Themes

| pain_point               |   Count |   Percentage |
|:-------------------------|--------:|-------------:|
| Other                    |     463 |         33.5 |
| Pricing & Fees           |     354 |         25.6 |
| Product Quality & Trust  |     158 |         11.4 |
| Delivery Experience      |     131 |          9.5 |
| Inventory & Availability |      94 |          6.8 |
| App Experience           |      60 |          4.3 |
| Returns & Refunds        |      55 |          4   |
| Service Availability     |      36 |          2.6 |
| Search & Discovery       |      31 |          2.2 |

## 6. Recurring User-Need Themes

| user_need                  |   Count |   Percentage |
|:---------------------------|--------:|-------------:|
| Other                      |     582 |         34.1 |
| Better Pricing             |     385 |         22.6 |
| Better Delivery            |     245 |         14.4 |
| Better Product Quality     |     188 |         11   |
| Better Availability        |     188 |         11   |
| Better Returns & Support   |      69 |          4   |
| Better Discovery           |      37 |          2.2 |
| Better Search & Navigation |      13 |          0.8 |

## 7. Product Features Mentioned

| feature            |   Count |   Percentage |
|:-------------------|--------:|-------------:|
| General Experience |     726 |         32.5 |
| Inventory          |     410 |         18.4 |
| Pricing            |     355 |         15.9 |
| Delivery           |     283 |         12.7 |
| Categories         |     135 |          6   |
| Checkout           |      94 |          4.2 |
| Offers             |      80 |          3.6 |
| Search             |      78 |          3.5 |
| Cart               |      26 |          1.2 |
| Homepage           |      25 |          1.1 |
| Recommendations    |      21 |          0.9 |

## 8. Categories Mentioned

| category_mentioned   |   Count |   Percentage |
|:---------------------|--------:|-------------:|
| Groceries            |     697 |         51.6 |
| Electronics          |     331 |         24.5 |
| Snacks & Beverages   |     185 |         13.7 |
| Personal Care        |      67 |          5   |
| Household Essentials |      53 |          3.9 |
| Medicines            |      15 |          1.1 |
| Baby Care            |       3 |          0.2 |
| Pet Care             |       1 |          0.1 |

## 9. Exploration Barrier × Category

| category_mentioned   |   App Experience |   Habit |   Lack of Awareness |   Limited Information |   No Need |   Poor Recommendations |   Price Concern |   Trust |
|:---------------------|-----------------:|--------:|--------------------:|----------------------:|----------:|-----------------------:|----------------:|--------:|
| Baby Care            |                0 |       2 |                   0 |                     0 |         0 |                      0 |               0 |       1 |
| Electronics          |                7 |      13 |                  27 |                    37 |         6 |                      0 |              38 |      59 |
| Groceries            |               23 |      89 |                  37 |                    25 |        12 |                      0 |             155 |     170 |
| Household Essentials |                7 |       3 |                   5 |                     4 |         0 |                      0 |              11 |       6 |
| Medicines            |                3 |       0 |                   1 |                     0 |         0 |                      0 |               1 |       1 |
| Personal Care        |               15 |       1 |                   2 |                     2 |         0 |                      0 |               8 |      24 |
| Pet Care             |                0 |       0 |                   1 |                     0 |         0 |                      0 |               0 |       0 |
| Snacks & Beverages   |                8 |       8 |                  43 |                    17 |         0 |                      1 |              22 |      24 |

## 10. Exploration Barrier × Product Feature

| feature            |   App Experience |   Habit |   Lack of Awareness |   Limited Information |   No Need |   Poor Recommendations |   Price Concern |   Trust |
|:-------------------|-----------------:|--------:|--------------------:|----------------------:|----------:|-----------------------:|----------------:|--------:|
| Cart               |               10 |       3 |                   0 |                     0 |         1 |                      0 |               5 |       5 |
| Categories         |                7 |       8 |                  26 |                    20 |         2 |                      0 |               2 |      19 |
| Checkout           |               21 |       0 |                   0 |                     1 |         0 |                      0 |              27 |      37 |
| Delivery           |               45 |       7 |                   7 |                     3 |         3 |                      0 |              22 |      62 |
| General Experience |               29 |     106 |                  37 |                    11 |        17 |                      0 |              19 |     107 |
| Homepage           |                5 |       1 |                   7 |                     0 |         0 |                      0 |               0 |       1 |
| Inventory          |               26 |      15 |                  53 |                    56 |         1 |                      0 |               2 |     166 |
| Offers             |                3 |       3 |                   4 |                     3 |         0 |                      1 |              44 |       2 |
| Pricing            |                2 |       4 |                   1 |                     2 |         0 |                      0 |             303 |       8 |
| Recommendations    |                0 |       2 |                  11 |                     2 |         0 |                      0 |               0 |       0 |
| Search             |               11 |       0 |                  27 |                    16 |         0 |                      0 |               2 |       2 |

## 11. Exploration Barrier × Sentiment

| exploration_barrier   |   Mixed |   Negative |   Neutral |   Positive |
|:----------------------|--------:|-----------:|----------:|-----------:|
| App Experience        |      11 |        105 |        33 |         10 |
| Habit                 |       3 |         21 |        86 |         39 |
| Lack of Awareness     |       2 |         45 |        82 |         44 |
| Limited Information   |      11 |         44 |        54 |          5 |
| No Need               |       2 |          8 |        12 |          2 |
| Poor Recommendations  |       0 |          1 |         0 |          0 |
| Price Concern         |      36 |        252 |       100 |         38 |
| Trust                 |      26 |        315 |        55 |         13 |