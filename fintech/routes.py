from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from fintech.db import db

bp = Blueprint("main", __name__)

MONTHS = [
    (1, "jan"), (2, "fev"), (3, "mar"), (4, "abr"),
    (5, "mai"), (6, "jun"), (7, "jul"), (8, "ago"),
    (9, "set"), (10, "out"), (11, "nov"), (12, "dez"),
]


def _require_user():
    return session.get("user_id")


def _parse_amount(raw_value):
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


@bp.route("/")
def index():
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("main.login"))

    month = request.args.get("mes", type=int)
    if month is not None and not (1 <= month <= 12):
        month = None

    conn = db.get_connection()
    total_income = 0
    total_expense = 0
    balance = 0
    margin_pct = 0.0
    categories_breakdown = []
    monthly_income = [0.0] * 12
    monthly_expense = [0.0] * 12
    recent_transactions = []

    try:
        with conn.cursor() as cur:
            month_clause = ""
            params = [user_id]
            if month is not None:
                month_clause = " AND EXTRACT(MONTH FROM t.transaction_at) = %s"
                params.append(month)

            cur.execute(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN c.type = 'receita' THEN t.amount ELSE 0 END), 0) AS total_receitas,
                    COALESCE(SUM(CASE WHEN c.type = 'despesa' THEN t.amount ELSE 0 END), 0) AS total_despesas
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s
                {month_clause};
                """,
                params,
            )
            summary = cur.fetchone()
            if summary:
                total_income = summary["total_receitas"]
                total_expense = summary["total_despesas"]
                balance = total_income - total_expense
                if total_income and float(total_income) > 0:
                    margin_pct = round((float(balance) / float(total_income)) * 100, 1)

            cur.execute(
                f"""
                SELECT c.name AS category_name, SUM(t.amount) AS total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s AND c.type = 'despesa'
                {month_clause}
                GROUP BY c.name
                ORDER BY total DESC;
                """,
                params,
            )
            raw_cats = cur.fetchall()

            total_expense_f = float(total_expense) if total_expense else 0.0
            top_value = float(raw_cats[0]["total"]) if raw_cats else 0.0

            for row in raw_cats:
                val = float(row["total"])
                categories_breakdown.append({
                    "category_name": row["category_name"],
                    "total": row["total"],
                    "pct_total": round((val / total_expense_f) * 100, 1) if total_expense_f > 0 else 0.0,
                    "pct_barra": round((val / top_value) * 100, 1) if top_value > 0 else 0.0,
                })

            cur.execute(
                f"""
                SELECT t.id, t.amount, t.description, t.transaction_at,
                       c.name AS category_name, c.type AS category_type
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s
                {month_clause}
                ORDER BY t.transaction_at DESC, t.id DESC
                LIMIT 5;
                """,
                params,
            )
            recent_transactions = cur.fetchall()

            # Série anual completa alimenta o gráfico comparativo independente do filtro mensal.
            cur.execute(
                """
                SELECT
                    EXTRACT(MONTH FROM t.transaction_at)::int AS month_num,
                    COALESCE(SUM(CASE WHEN c.type = 'receita' THEN t.amount ELSE 0 END), 0) AS receitas,
                    COALESCE(SUM(CASE WHEN c.type = 'despesa' THEN t.amount ELSE 0 END), 0) AS despesas
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s
                GROUP BY month_num
                ORDER BY month_num;
                """,
                (user_id,),
            )
            for row in cur.fetchall():
                idx = row["month_num"] - 1
                if 0 <= idx < 12:
                    monthly_income[idx] = float(row["receitas"])
                    monthly_expense[idx] = float(row["despesas"])
    except Exception as exc:
        flash(f"Não foi possível carregar o resumo: {exc}", "error")
    finally:
        db.put_connection(conn)

    return render_template(
        "index.html",
        total_receitas=total_income,
        total_despesas=total_expense,
        saldo=balance,
        margem_lucro_pct=margin_pct,
        mes_selecionado=month,
        meses=MONTHS,
        despesas_por_categoria=categories_breakdown,
        receitas_mensais=monthly_income,
        despesas_mensais=monthly_expense,
        ultimas_transacoes=recent_transactions,
    )


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Informe email e senha.", "error")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
                if cur.fetchone():
                    flash("Este email já está cadastrado.", "error")
                    return redirect(url_for("main.register"))

                cur.execute(
                    "INSERT INTO users (email, password) VALUES (%s, %s);",
                    (email, password_hash),
                )
                conn.commit()

            flash("Conta criada. Faça login para continuar.", "success")
            return redirect(url_for("main.login"))
        except Exception as exc:
            conn.rollback()
            flash(f"Erro ao criar conta: {exc}", "error")
        finally:
            db.put_connection(conn)

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, email, password FROM users WHERE email = %s;", (email,))
                user = cur.fetchone()

                if user and check_password_hash(user["password"], password):
                    session["user_id"] = user["id"]
                    session["user_email"] = user["email"]
                    return redirect(url_for("main.index"))

                flash("Email ou senha inválidos.", "error")
        except Exception as exc:
            logger.exception("Login error: %s", exc)
            flash("Erro ao autenticar. Tente novamente.", "error")
        finally:
            db.put_connection(conn)

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/categories", methods=["GET", "POST"])
def categories():
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("main.login"))

    conn = db.get_connection()
    items = []
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                name = (request.form.get("name") or "").strip()
                cat_type = request.form.get("type")

                if not name or cat_type not in ("receita", "despesa"):
                    flash("Informe nome e tipo da categoria.", "error")
                else:
                    cur.execute(
                        "INSERT INTO categories (user_id, name, type) VALUES (%s, %s, %s);",
                        (user_id, name, cat_type),
                    )
                    conn.commit()
                    flash("Categoria salva.", "success")
                    return redirect(url_for("main.categories"))

            cur.execute(
                "SELECT id, name, type FROM categories WHERE user_id = %s ORDER BY name ASC;",
                (user_id,),
            )
            items = cur.fetchall()
    except Exception as exc:
        conn.rollback()
        flash(f"Erro ao carregar categorias: {exc}", "error")
    finally:
        db.put_connection(conn)

    return render_template("categories.html", categories=items)


@bp.route("/categories/<int:category_id>/edit", methods=["POST"])
def edit_category(category_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("main.login"))

    name = (request.form.get("name") or "").strip()
    cat_type = request.form.get("type")
    if not name or cat_type not in ("receita", "despesa"):
        flash("Informe nome e tipo da categoria.", "error")
        return redirect(url_for("main.categories"))

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE categories
                SET name = %s, type = %s
                WHERE id = %s AND user_id = %s;
                """,
                (name, cat_type, category_id, user_id),
            )
            if cur.rowcount == 0:
                flash("Categoria não encontrada.", "error")
            else:
                conn.commit()
                flash("Categoria atualizada.", "success")
    except Exception as exc:
        conn.rollback()
        flash(f"Erro ao atualizar categoria: {exc}", "error")
    finally:
        db.put_connection(conn)

    return redirect(url_for("main.categories"))


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("main.login"))

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM transactions WHERE category_id = %s;",
                (category_id,),
            )
            row = cur.fetchone()
            if row and row["total"] > 0:
                flash("Categoria possui transações vinculadas e não pode ser excluída.", "error")
                return redirect(url_for("main.categories"))

            cur.execute(
                "DELETE FROM categories WHERE id = %s AND user_id = %s;",
                (category_id, user_id),
            )
            if cur.rowcount == 0:
                flash("Categoria não encontrada.", "error")
            else:
                conn.commit()
                flash("Categoria excluída.", "success")
    except Exception as exc:
        conn.rollback()
        flash(f"Erro ao excluir categoria: {exc}", "error")
    finally:
        db.put_connection(conn)

    return redirect(url_for("main.categories"))


@bp.route("/transactions", methods=["GET", "POST"])
def transactions():
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("main.login"))

    tx_filter = request.args.get("tipo")
    if tx_filter not in ("receita", "despesa"):
        tx_filter = None

    conn = db.get_connection()
    cats = []
    txs = []
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                description = (request.form.get("description") or "").strip()
                category_id = request.form.get("category_id", type=int)
                amount = _parse_amount(request.form.get("amount"))

                if amount is None:
                    flash("Informe um valor maior que zero.", "error")
                    return redirect(url_for("main.transactions"))

                if not description or not category_id:
                    flash("Preencha descrição e categoria.", "error")
                else:
                    cur.execute(
                        "SELECT id FROM categories WHERE id = %s AND user_id = %s;",
                        (category_id, user_id),
                    )
                    if not cur.fetchone():
                        flash("Categoria inválida.", "error")
                    else:
                        cur.execute(
                            "INSERT INTO transactions (category_id, amount, description) VALUES (%s, %s, %s);",
                            (category_id, amount, description),
                        )
                        conn.commit()
                        flash("Transação registrada.", "success")
                        return redirect(url_for("main.transactions"))

            cur.execute(
                "SELECT id, name, type FROM categories WHERE user_id = %s ORDER BY name ASC;",
                (user_id,),
            )
            cats = cur.fetchall()

            sql = """
                SELECT t.id, t.category_id, t.amount, t.description, t.transaction_at,
                       c.name AS category_name, c.type AS category_type
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s
            """
            params = [user_id]
            if tx_filter:
                sql += " AND c.type = %s"
                params.append(tx_filter)
            sql += " ORDER BY t.transaction_at DESC, t.id DESC;"

            cur.execute(sql, params)
            txs = cur.fetchall()
    except Exception as exc:
        conn.rollback()
        flash(f"Erro ao carregar transações: {exc}", "error")
    finally:
        db.put_connection(conn)

    return render_template(
        "transactions.html",
        categories=cats,
        transactions=txs,
        filtro_atual=tx_filter,
    )


@bp.route("/transactions/<int:transaction_id>/edit", methods=["POST"])
def edit_transaction(transaction_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("main.login"))

    description = (request.form.get("description") or "").strip()
    category_id = request.form.get("category_id", type=int)
    amount = _parse_amount(request.form.get("amount"))

    if amount is None:
        flash("Informe um valor maior que zero.", "error")
        return redirect(url_for("main.transactions"))

    if not description or not category_id:
        flash("Preencha descrição e categoria.", "error")
        return redirect(url_for("main.transactions"))

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM categories WHERE id = %s AND user_id = %s;",
                (category_id, user_id),
            )
            if not cur.fetchone():
                flash("Categoria inválida.", "error")
                return redirect(url_for("main.transactions"))

            cur.execute(
                """
                UPDATE transactions t
                SET amount = %s, description = %s, category_id = %s
                FROM categories c
                WHERE t.id = %s
                  AND t.category_id = c.id
                  AND c.user_id = %s;
                """,
                (amount, description, category_id, transaction_id, user_id),
            )
            if cur.rowcount == 0:
                flash("Transação não encontrada.", "error")
            else:
                conn.commit()
                flash("Transação atualizada.", "success")
    except Exception as exc:
        conn.rollback()
        flash(f"Erro ao atualizar transação: {exc}", "error")
    finally:
        db.put_connection(conn)

    return redirect(url_for("main.transactions"))


@bp.route("/transactions/<int:transaction_id>/delete", methods=["POST"])
def delete_transaction(transaction_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("main.login"))

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM transactions t
                USING categories c
                WHERE t.id = %s
                  AND t.category_id = c.id
                  AND c.user_id = %s;
                """,
                (transaction_id, user_id),
            )
            if cur.rowcount == 0:
                flash("Transação não encontrada.", "error")
            else:
                conn.commit()
                flash("Transação excluída.", "success")
    except Exception as exc:
        conn.rollback()
        flash(f"Erro ao excluir transação: {exc}", "error")
    finally:
        db.put_connection(conn)

    return redirect(url_for("main.transactions"))