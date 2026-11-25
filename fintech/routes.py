from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from fintech.db import db

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    mes = request.args.get('mes', type=int)
    if mes is not None and (mes < 1 or mes > 12):
        mes = None

    conn = db.get_connection()
    total_receitas = 0
    total_despesas = 0
    saldo = 0
    margem_lucro_pct = 0.0
    despesas_por_categoria = []
    receitas_mensais = [0.0] * 12
    despesas_mensais = [0.0] * 12
    ultimas_transacoes = []

    try:
        with conn.cursor() as cursor:
            filtro_mes_sql = ""
            params_resumo = [user_id]

            if mes is not None:
                filtro_mes_sql = " AND EXTRACT(MONTH FROM t.transaction_at) = %s"
                params_resumo.append(mes)

            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(CASE WHEN c.type = 'receita' THEN t.amount ELSE 0 END), 0) AS total_receitas,
                    COALESCE(SUM(CASE WHEN c.type = 'despesa' THEN t.amount ELSE 0 END), 0) AS total_despesas
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s
                {filtro_mes_sql};
            """, params_resumo)

            resumo = cursor.fetchone()
            if resumo:
                total_receitas = resumo['total_receitas']
                total_despesas = resumo['total_despesas']
                saldo = total_receitas - total_despesas
                if total_receitas and float(total_receitas) > 0:
                    margem_lucro_pct = round((float(saldo) / float(total_receitas)) * 100, 1)

            params_cat = [user_id]
            if mes is not None:
                params_cat.append(mes)

            cursor.execute(f"""
                SELECT c.name AS category_name, SUM(t.amount) AS total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s AND c.type = 'despesa'
                {filtro_mes_sql}
                GROUP BY c.name
                ORDER BY total DESC;
            """, params_cat)
            raw_categorias = cursor.fetchall()

            total_despesas_float = float(total_despesas) if total_despesas else 0.0
            maior_valor = float(raw_categorias[0]['total']) if raw_categorias else 0.0

            for item in raw_categorias:
                valor_float = float(item['total'])
                pct_total = round((valor_float / total_despesas_float) * 100, 1) if total_despesas_float > 0 else 0.0
                pct_barra = round((valor_float / maior_valor) * 100, 1) if maior_valor > 0 else 0.0
                despesas_por_categoria.append({
                    'category_name': item['category_name'],
                    'total': item['total'],
                    'pct_total': pct_total,
                    'pct_barra': pct_barra
                })

            params_ult = [user_id]
            if mes is not None:
                params_ult.append(mes)

            cursor.execute(f"""
                SELECT t.id, t.amount, t.description, t.transaction_at, c.name AS category_name, c.type AS category_type
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s
                {filtro_mes_sql}
                ORDER BY t.transaction_at DESC, t.id DESC
                LIMIT 5;
            """, params_ult)
            ultimas_transacoes = cursor.fetchall()

            # Evolução mensal (jan..dez) para receitas e despesas
            cursor.execute("""
                SELECT
                    EXTRACT(MONTH FROM t.transaction_at)::int AS mes_num,
                    COALESCE(SUM(CASE WHEN c.type = 'receita' THEN t.amount ELSE 0 END), 0) AS receitas,
                    COALESCE(SUM(CASE WHEN c.type = 'despesa' THEN t.amount ELSE 0 END), 0) AS despesas
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s
                GROUP BY mes_num
                ORDER BY mes_num;
            """, (user_id,))

            for linha in cursor.fetchall():
                idx = linha['mes_num'] - 1
                if 0 <= idx < 12:
                    receitas_mensais[idx] = float(linha['receitas'])
                    despesas_mensais[idx] = float(linha['despesas'])

    except Exception as e:
        flash(f"Erro ao calcular dados do dashboard: {e}", "error")
    finally:
        db.put_connection(conn)

    meses = [
        (1, 'jan'), (2, 'fev'), (3, 'mar'), (4, 'abr'),
        (5, 'mai'), (6, 'jun'), (7, 'jul'), (8, 'ago'),
        (9, 'set'), (10, 'out'), (11, 'nov'), (12, 'dez')
    ]

    return render_template(
        'index.html',
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        saldo=saldo,
        margem_lucro_pct=margem_lucro_pct,
        mes_selecionado=mes,
        meses=meses,
        despesas_por_categoria=despesas_por_categoria,
        receitas_mensais=receitas_mensais,
        despesas_mensais=despesas_mensais,
        ultimas_transacoes=ultimas_transacoes
    )


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        hashed_password = generate_password_hash(password)

        conn = db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash("Este email já está registado!", "error")
                    return redirect(url_for('main.register'))

                cursor.execute(
                    "INSERT INTO users (email, password) VALUES (%s, %s)",
                    (email, hashed_password)
                )
                conn.commit()

            flash("Conta criada com sucesso! Faça login.", "success")
            return redirect(url_for('main.login'))
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao registar: {e}", "error")
        finally:
            db.put_connection(conn)

    return render_template('register.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, email, password FROM users WHERE email = %s;", (email,))
                user = cursor.fetchone()

                if user and check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['user_email'] = user['email']
                    flash("Login efetuado com sucesso!", "success")
                    return redirect(url_for('main.index'))
                else:
                    flash("Email ou senha incorretos.", "error")
        except Exception as e:
            print(f"DETALHE DO ERRO NO LOGIN: {str(e)}")
            flash(f"Erro ao fazer login: {e}", "error")
        finally:
            db.put_connection(conn)

    return render_template('login.html')


@bp.route("/logout")
def logout():
    session.clear()
    flash("Sessão terminada com sucesso.", "success")
    return redirect(url_for("main.login"))


@bp.route('/categories', methods=['GET', 'POST'])
def categories():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    conn = db.get_connection()
    categories_list = []

    try:
        with conn.cursor() as cursor:
            if request.method == 'POST':
                name = (request.form.get('name') or '').strip()
                cat_type = request.form.get('type')

                if not name or cat_type not in ('receita', 'despesa'):
                    flash("Preencha o nome e um tipo válido para a categoria.", "error")
                else:
                    cursor.execute(
                        "INSERT INTO categories (user_id, name, type) VALUES (%s, %s, %s);",
                        (user_id, name, cat_type)
                    )
                    conn.commit()
                    flash("Categoria adicionada com sucesso!", "success")
                    return redirect(url_for('main.categories'))

            cursor.execute(
                "SELECT id, name, type FROM categories WHERE user_id = %s ORDER BY name ASC;",
                (user_id,)
            )
            categories_list = cursor.fetchall()
    except Exception as e:
        conn.rollback()
        flash(f"Erro nas categorias: {e}", "error")
    finally:
        db.put_connection(conn)

    return render_template('categories.html', categories=categories_list)


@bp.route('/categories/<int:category_id>/edit', methods=['POST'])
def edit_category(category_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    name = (request.form.get('name') or '').strip()
    cat_type = request.form.get('type')

    if not name or cat_type not in ('receita', 'despesa'):
        flash("Preencha o nome e um tipo válido para a categoria.", "error")
        return redirect(url_for('main.categories'))

    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE categories
                SET name = %s, type = %s
                WHERE id = %s AND user_id = %s;
            """, (name, cat_type, category_id, user_id))
            if cursor.rowcount == 0:
                flash("Categoria não encontrada.", "error")
            else:
                conn.commit()
                flash("Categoria atualizada com sucesso!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao atualizar categoria: {e}", "error")
    finally:
        db.put_connection(conn)

    return redirect(url_for('main.categories'))


@bp.route('/categories/<int:category_id>/delete', methods=['POST'])
def delete_category(category_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM transactions
                WHERE category_id = %s;
            """, (category_id,))
            row = cursor.fetchone()
            if row and row['total'] > 0:
                flash("Não é possível remover uma categoria que já possui transações associadas.", "error")
                return redirect(url_for('main.categories'))

            cursor.execute("""
                DELETE FROM categories
                WHERE id = %s AND user_id = %s;
            """, (category_id, user_id))
            if cursor.rowcount == 0:
                flash("Categoria não encontrada.", "error")
            else:
                conn.commit()
                flash("Categoria removida com sucesso!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao remover categoria: {e}", "error")
    finally:
        db.put_connection(conn)

    return redirect(url_for('main.categories'))


@bp.route('/transactions', methods=['GET', 'POST'])
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    filtro_tipo = request.args.get('tipo')
    if filtro_tipo not in ('receita', 'despesa'):
        filtro_tipo = None

    conn = db.get_connection()
    categories_list = []
    transactions_list = []

    try:
        with conn.cursor() as cursor:
            if request.method == 'POST':
                description = (request.form.get('description') or '').strip()
                category_id = request.form.get('category_id', type=int)

                try:
                    amount = float(request.form.get('amount'))
                    if amount <= 0:
                        raise ValueError()
                except (TypeError, ValueError):
                    flash("Informe um valor válido maior que zero.", "error")
                    return redirect(url_for('main.transactions'))

                if not description or not category_id:
                    flash("Preencha a descrição e selecione uma categoria.", "error")
                else:
                    cursor.execute(
                        "SELECT id FROM categories WHERE id = %s AND user_id = %s;",
                        (category_id, user_id)
                    )
                    if not cursor.fetchone():
                        flash("Categoria inválida para este utilizador.", "error")
                    else:
                        cursor.execute(
                            "INSERT INTO transactions (category_id, amount, description) VALUES (%s, %s, %s);",
                            (category_id, amount, description)
                        )
                        conn.commit()
                        flash("Transação adicionada com sucesso!", "success")
                        return redirect(url_for('main.transactions'))

            cursor.execute(
                "SELECT id, name, type FROM categories WHERE user_id = %s ORDER BY name ASC;",
                (user_id,)
            )
            categories_list = cursor.fetchall()

            sql_tx = """
                SELECT t.id, t.category_id, t.amount, t.description, t.transaction_at,
                       c.name AS category_name, c.type AS category_type
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s
            """
            params_tx = [user_id]
            if filtro_tipo:
                sql_tx += " AND c.type = %s"
                params_tx.append(filtro_tipo)
            sql_tx += " ORDER BY t.transaction_at DESC, t.id DESC;"

            cursor.execute(sql_tx, params_tx)
            transactions_list = cursor.fetchall()
    except Exception as e:
        conn.rollback()
        flash(f"Erro nas transações: {e}", "error")
    finally:
        db.put_connection(conn)

    return render_template(
        'transactions.html',
        categories=categories_list,
        transactions=transactions_list,
        filtro_atual=filtro_tipo
    )


@bp.route('/transactions/<int:transaction_id>/edit', methods=['POST'])
def edit_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    description = (request.form.get('description') or '').strip()
    category_id = request.form.get('category_id', type=int)

    try:
        amount = float(request.form.get('amount'))
        if amount <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        flash("Informe um valor válido maior que zero.", "error")
        return redirect(url_for('main.transactions'))

    if not description or not category_id:
        flash("Preencha a descrição e selecione uma categoria.", "error")
        return redirect(url_for('main.transactions'))

    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM categories WHERE id = %s AND user_id = %s;
            """, (category_id, user_id))
            if not cursor.fetchone():
                flash("Categoria inválida para este utilizador.", "error")
                return redirect(url_for('main.transactions'))

            cursor.execute("""
                UPDATE transactions t
                SET amount = %s, description = %s, category_id = %s
                FROM categories c
                WHERE t.id = %s
                  AND t.category_id = c.id
                  AND c.user_id = %s;
            """, (amount, description, category_id, transaction_id, user_id))

            if cursor.rowcount == 0:
                flash("Transação não encontrada.", "error")
            else:
                conn.commit()
                flash("Transação atualizada com sucesso!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao atualizar transação: {e}", "error")
    finally:
        db.put_connection(conn)

    return redirect(url_for('main.transactions'))


@bp.route('/transactions/<int:transaction_id>/delete', methods=['POST'])
def delete_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM transactions t
                USING categories c
                WHERE t.id = %s
                  AND t.category_id = c.id
                  AND c.user_id = %s;
            """, (transaction_id, user_id))

            if cursor.rowcount == 0:
                flash("Transação não encontrada.", "error")
            else:
                conn.commit()
                flash("Transação removida com sucesso!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao remover transação: {e}", "error")
    finally:
        db.put_connection(conn)

    return redirect(url_for('main.transactions'))