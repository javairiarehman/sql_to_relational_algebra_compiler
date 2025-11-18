import sqlparse
import sqlparse.tokens as T 
from radb.ast import Project, RelRef, AttrRef, Cross, Rename, Select
from radb.ast import ValExprBinaryOp, RAString, RANumber 
from radb.parse import RAParser as sym 
QUERY = "select distinct Person.name, pizzeria from Person, Eats, Serves where Person.name = Eats.name and Eats.pizza = Serves.pizza"
stmt = sqlparse.parse(QUERY)[0]

#print(stmt)

def _get_ttype(token):
    return getattr(token, 'ttype', getattr(token, 'type', None))

def _is_keyword_or_dml(token_type):
    return (token_type is not None and T.Keyword in token_type) or \
           (token_type is not None and T.DML in token_type)

def _collect_between_keywords(statement, start_keyword, stop_keywords=None):

    tokens = statement.tokens
    start_found = False
    collected = []
    stop_keywords = set([k.upper() for k in (stop_keywords or [])])

    for token in tokens:
        token_text = getattr(token, "value", "").upper().strip()
        if not start_found and token_text == start_keyword.upper():
            start_found = True
            continue

        if start_found:
            if token_text in stop_keywords and _is_keyword_or_dml(_get_ttype(token)):
                break

        
            if _get_ttype(token) == T.Whitespace:
                continue
            collected.append(token)

    return collected

def _convert_projection(statement):
    sel_tokens = _collect_between_keywords(statement, "SELECT", stop_keywords={"FROM"})
    if not sel_tokens:
        return []
    flat = []
    for tok in sel_tokens:
        if tok.is_group:
            for inner in tok.flatten():
                if _get_ttype(inner) not in [T.Whitespace]:
                    flat.append(inner)
        else:
            if _get_ttype(tok) not in [T.Whitespace]:
                flat.append(tok)
    attrs = []
    i = 0
    while i < len(flat):
        tok = flat[i]
        ttype = _get_ttype(tok)
        val = tok.value.strip()
        if i + 2 < len(flat) and ttype == T.Name and flat[i+1].value.strip() == '.' and _get_ttype(flat[i+2]) == T.Name:
            rel = flat[i].value.strip()
            attr = flat[i+2].value.strip()
            attrs.append(AttrRef(rel, attr))
            i += 3
            continue
        if '.' in val:
            parts = val.split('.')
            if len(parts) == 2:
                attrs.append(AttrRef(parts[0], parts[1]))
                i += 1
                continue

        if ttype == T.Name:
            attrs.append(AttrRef(None, val))
        i += 1

    return attrs

def _convert_single_comparison(token):   
    raw_parts = [t for t in token.flatten() if _get_ttype(t) not in [T.Whitespace]]
    semantic_parts = []
    i = 0
    while i < len(raw_parts):
        part = raw_parts[i]
        part_type = _get_ttype(part)
        if i + 2 < len(raw_parts) and part_type == T.Name and raw_parts[i+1].value.strip() == '.' and _get_ttype(raw_parts[i+2]) == T.Name:
            qualified_name = f"{part.value.strip()}.{raw_parts[i+2].value.strip()}"
            semantic_parts.append(qualified_name)
            i += 3
        elif part_type == T.Comparison or part_type == T.Literal.String.Single or part_type == T.Literal.Number.Integer or part_type == T.Name:
            semantic_parts.append(part.value.strip())
            i += 1
        else:
            i += 1
    if len(semantic_parts) != 3: 
        raise ValueError(f"Invalid comparison format. Expected 3 parts after reassembly, found {len(semantic_parts)}. Parts: {semantic_parts}")

    op = sym.EQ 
    
    def _get_operand(value):
        if '.' in value:
            parts = value.split('.')
            return AttrRef(parts[0], parts[1])
        if value.startswith("'") and value.endswith("'"):
            return RAString(value)
        try:
            int(value)
            return RANumber(value)
        except Exception:
            return AttrRef(None, value) 

    left_operand = _get_operand(semantic_parts[0])
    right_operand = _get_operand(semantic_parts[2])
    return ValExprBinaryOp(left_operand, op, right_operand)

def _build_selection_condition(statement):
    """Builds the Selection AST by finding the WHERE comparison(s) and combining with AND if needed."""
    where_group = None
    for token in statement.tokens:
        if token.is_group and (token.get_type() if hasattr(token, 'get_type') else token.__class__.__name__) == 'Where':
            where_group = token
            break

    if where_group is None:
        return None
    comparisons = []
    for t in where_group.tokens:
        if t.__class__.__name__ == 'Comparison':
            comparisons.append(t)
        elif hasattr(t, 'tokens') and t.is_group:
            for inner in t.tokens:
                if inner.__class__.__name__ == 'Comparison':
                    comparisons.append(inner)

    if not comparisons:
        return None

    exprs = [_convert_single_comparison(c) for c in comparisons]

    if len(exprs) == 1:
        return exprs[0]
    curr = exprs[0]
    for nxt in exprs[1:]:
        curr = ValExprBinaryOp(curr, sym.AND, nxt)
    return curr

def _build_base_relations(statement):
    from_tokens = _collect_between_keywords(statement, "FROM", stop_keywords={"WHERE", "GROUP", "ORDER", "HAVING"})
    if not from_tokens:
        raise ValueError("FROM clause is empty or improperly structured.")

    relations = []
    for token in from_tokens:
        cls = token.__class__.__name__
        if cls == 'IdentifierList':
            if hasattr(token, 'get_identifiers'):
                for ident in token.get_identifiers():
                    real = ident.get_real_name() if hasattr(ident, 'get_real_name') else None
                    alias = ident.get_alias() if hasattr(ident, 'get_alias') else None
                    if not real:
                        for inner in ident.tokens:
                            if _get_ttype(inner) == T.Name:
                                real = inner.value.strip()
                                break
                    if real:
                        r = RelRef(real)
                        if alias and alias != real:
                            r = Rename(r, alias)
                        relations.append(r)
            else:
                pieces = [p.strip() for p in token.value.split(',') if p.strip()]
                for p in pieces:
                    if '.' in p:
                        continue
                    parts = p.split()
                    real = parts[0]
                    alias = parts[1] if len(parts) > 1 else None
                    r = RelRef(real)
                    if alias:
                        r = Rename(r, alias)
                    relations.append(r)
            continue
        if cls == 'Identifier':
            real = token.get_real_name() if hasattr(token, 'get_real_name') else None
            alias = token.get_alias() if hasattr(token, 'get_alias') else None
            if not real:
                for inner in token.tokens:
                    if _get_ttype(inner) == T.Name:
                        real = inner.value.strip()
                        break
            if real:
                r = RelRef(real)
                if alias and alias != real:
                    r = Rename(r, alias)
                relations.append(r)
            continue
        if _get_ttype(token) == T.Name:
            val = token.value.strip()
            if '.' in val:
                continue
            relations.append(RelRef(val))
            continue
        val = token.value.strip()
        if ',' in val:
            pieces = [p.strip() for p in val.split(',') if p.strip()]
            for p in pieces:
                if '.' in p:
                    continue
                parts = p.split()
                real = parts[0]
                alias = parts[1] if len(parts) > 1 else None
                r = RelRef(real)
                if alias:
                    r = Rename(r, alias)
                relations.append(r)
            continue
    unique = []
    seen = set()
    for r in relations:
        key = str(r)
        if key not in seen:
            unique.append(r)
            seen.add(key)

    if not unique:
        raise ValueError("FROM clause parsing produced no relations.")
    expr = unique[0]
    for r in unique[1:]:
        expr = Cross(expr, r)
    return expr


def build_full_test_ra():
    base_expression = _build_base_relations(stmt)
    condition_ast = _build_selection_condition(stmt)
    
    if condition_ast:
        expression_after_select = Select(condition_ast, base_expression)
    else:
        expression_after_select = base_expression
    projection_attributes = _convert_projection(stmt)
    
    if not projection_attributes:
        final_ra_ast = expression_after_select
    else:
        final_ra_ast = Project(projection_attributes, expression_after_select)
        
    print("\nFiRA Expression Assembly:")
    print(f"Final Expression: {final_ra_ast}")
    print(f"Type: {final_ra_ast.__class__.__name__}")
    
if __name__ == '__main__':
    build_full_test_ra()
