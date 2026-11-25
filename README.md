# FintechDash

## About

A multi-user personal finance control system developed in **Python (Flask)** and **PostgreSQL**, featuring metrics and cash flow visualization via an interactive dashboard.

## Features

* **Authentication & Session Management**: User registration (`/register`), login (`/login`), password hashing via `werkzeug.security`, session handling (`session`), and logout (`/logout`).
* **Monthly & Cumulative Dashboard (`/`)**:
  * Filter metrics and cash flow by month (`jan` through `dec`) or view accumulated totals (`todos`) using SQL `EXTRACT(MONTH FROM ...)`.
  * Key KPIs: Total Expenses, Total Income, Profit/Result Margin (`%`), and Net Balance.
  * Interactive **Chart.js** visualizations: Monthly Operational Evolution (Income vs. Expenses bar chart) and Expenses by Category (doughnut chart).
  * Analytical category breakdown table with percentage share and proportional progress bars, plus a **Recent Transactions** widget.
* **Category Management (`/categories`)**: Create, edit (inline), and delete income/expense categories scoped to the authenticated user, with protection against deleting categories that have linked transactions.
* **Transaction Management & Ledger (`/transactions`)**: Create, edit (inline), delete, and filter transactions by type (`Todas`, `Receitas`, `Despesas`).
* **Light Mode Primary + Dark Mode Toggle**: Defaults to a crisp light theme (`#E3F2FD` background with high-contrast white cards) and supports switching to dark mode via `localStorage` (`fintech_theme`), updating charts dynamically.

## Project Architecture

```text
fintech-dashboard-flask/
├── fintech/
│   ├── __init__.py        # Application Factory & configuration
│   ├── db.py              # PostgreSQL connection pool (psycopg2 / RealDictCursor)
│   └── routes.py          # Blueprint routes ('main') for auth, dashboard, CRUD
├── templates/
│   ├── base.html          # Base layout, Tailwind CSS v4 config, theme toggle & navbar
│   ├── index.html         # Executive dashboard, filters, KPIs, charts & tables
│   ├── categories.html    # Category creation, inline editing & deletion
│   ├── transactions.html  # Transaction creation, inline editing, deletion & filters
│   ├── login.html         # User sign-in view
│   └── register.html      # User registration view
└── README.md
