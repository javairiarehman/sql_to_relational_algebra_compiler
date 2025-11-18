

🐍 SQL to Relational Algebra Compiler
A simple Python script that translates a subset of SQL SELECT queries into a corresponding Relational Algebra (RA) Abstract Syntax Tree (AST) using the sqlparse library for SQL tokenization and the radb.ast library for RA structure.
🎯 Features
Parses SELECT queries with FROM and WHERE clauses.
Handles Cross Product (Cartesian product) for relations listed in the FROM clause.
Translates WHERE clause conditions into Selection ($\sigma$) operations.
Converts SELECT clause attributes into Projection ($\pi$) operations.
Supports qualified attributes (e.g., Relation.attribute).
Processes simple equality comparisons in the WHERE clause.
⚙️ Prerequisites
This script requires two external libraries:
sqlparse: For tokenizing and grouping SQL statements.
radb: A library providing the Abstract Syntax Tree (AST) classes for Relational Algebra.
You can install them using pip:
Bash
pip install sqlparse
pip install radb

🛠️ Usage
1. Define the Query
The script is currently configured to process a hardcoded query defined by the QUERY variable:
Python
QUERY = "select distinct Person.name, pizzeria from Person, Eats, Serves where Person.name = Eats.name and Eats.pizza = Serves.pizza"

2. Run the Script
Execute the Python script directly:
Bash
python compiler.py

3. Output
The script will print the final generated Relational Algebra AST, structured as a series of nested RA operations.
Example Output for the hardcoded query:
FiRA Expression Assembly:
Final Expression: Project([Person.name, pizzeria], Select(Person.name = Eats.name AND Eats.pizza = Serves.pizza, Cross(Cross(RelRef(Person), RelRef(Eats)), RelRef(Serves))))
Type: Project


💻 Implementation Details
The core functionality is implemented through a series of modular functions:
_collect_between_keywords(statement, start_keyword, stop_keywords=None): Helper to extract tokens between two specific keywords (e.g., tokens between SELECT and FROM).
_convert_projection(statement): Parses the SELECT clause tokens and constructs a list of AttrRef (Attribute Reference) objects for the final Projection operation.
_convert_single_comparison(token): Converts a single SQL comparison token (e.g., Person.name = Eats.name) into a Relational Algebra expression object (ValExprBinaryOp).
_build_selection_condition(statement): Scans the WHERE clause for all comparison tokens and combines them with the AND operator (sym.AND) into a single complex condition for the Selection ($\sigma$) operator.
_build_base_relations(statement): Parses the FROM clause to build the initial relational expression. It creates RelRef (Relation Reference) objects and combines them using the Cross Product ($\times$) operator.
build_full_test_ra(): The main function that orchestrates the parsing process, applying the operators in the correct order:
Cross Product (from FROM)
Selection (from WHERE)
Projection (from SELECT)
💡 Key Design Point
The compilation follows the fundamental transformation for a simple $\text{SELECT} \dots \text{FROM} \dots \text{WHERE} \dots$ query:
$$\pi_{\text{select\_list}} \left( \sigma_{\text{where\_condition}} \left( R_1 \times R_2 \times \dots \times R_n \right) \right)$$
where $R_1, R_2, \dots, R_n$ are the relations in the FROM clause.
# sql_to_relational_algebra_compiler
