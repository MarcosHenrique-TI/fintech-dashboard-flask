from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from fintech.db import db

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
        
    user_id = session['user_id']
    conn = db.get_connection()
    
    total_receitas = 0
    total_despesas = 0
    saldo = 0
    despesas_por_categoria = []
    
    try:
        with conn.cursor() as cursor:
            # Resumo total
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN c.type = 'receita' THEN t.amount ELSE 0 END), 0) as total_receitas,
                    COALESCE(SUM(CASE WHEN c.type = 'despesa' THEN t.amount ELSE 0 END), 0) as total_despesas
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s;
            """, (user_id,))
            resumo = cursor.fetchone()
            if resumo:
                total_receitas = resumo['total_receitas']
                total_despesas = resumo['total_despesas']
                saldo = total_receitas - total_despesas

            # Dados para o Gráfico (Despesas por Categoria)
            cursor.execute("""
                SELECT c.name as category_name, SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s AND c.type = 'despesa'
                GROUP BY c.name;
            """, (user_id,))
            despesas_por_categoria = cursor.fetchall()
            
    except Exception as e:
        flash(f"Erro ao calcular dados do dashboard: {e}", "error")
    finally:
        db.put_connection(conn)
        
    return render_template(
        'index.html', 
        total_receitas=total_receitas, 
        total_despesas=total_despesas, 
        saldo=saldo,
        despesas_por_categoria=despesas_por_categoria
    )
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Cria um hash seguro para a senha
        hashed_password = generate_password_hash(password)
        
        conn = db.get_connection()
        try:
            with conn.cursor() as cursor:
                # Verifica se o email já existe
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash("Este email já está registado!", "error")
                    return redirect(url_for('main.register'))
                
                # Insere o novo utilizador na base de dados
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
                
                # Como usamos RealDictCursor, 'user' é um dicionário. 
                # Acedemos por chave: user['password'], user['id'], user['email']
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
    session.clear() # Limpa a sessão do utilizador
    flash("Sessão terminada com sucesso.", "success")
    return redirect(url_for("main.login"))

@bp.route('/categories', methods=['GET', 'POST'])
def categories():
    # Garante que o utilizador está autenticado
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
        
    user_id = session['user_id']
    conn = db.get_connection()
    
    if request.method == 'POST':
        name = request.form.get('name')
        cat_type = request.form.get('type') # 'receita' ou 'despesa'
        
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO categories (name, type, user_id) VALUES (%s, %s, %s)",
                    (name, cat_type, user_id)
                )
                conn.commit()
            flash("Categoria criada com sucesso!", "success")
            return redirect(url_for('main.categories'))
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao criar categoria: {e}", "error")
            
    # Listar as categorias do utilizador logado
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, type FROM categories WHERE user_id = %s ORDER BY id DESC;", (user_id,))
            user_categories = cursor.fetchall()
    except Exception as e:
        user_categories = []
        flash(f"Erro ao carregar categorias: {e}", "error")
    finally:
        db.put_connection(conn)
        
    return render_template('categories.html', categories=user_categories)

@bp.route('/transactions', methods=['GET', 'POST'])
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
        
    user_id = session['user_id']
    conn = db.get_connection()
    
    if request.method == 'POST':
        amount = request.form.get('amount')
        description = request.form.get('description')
        category_id = request.form.get('category_id')
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM categories WHERE id = %s AND user_id = %s", (category_id, user_id))
                if not cursor.fetchone():
                    flash("Categoria inválida.", "error")
                    return redirect(url_for('main.transactions'))
                    
                cursor.execute(
                    "INSERT INTO transactions (amount, description, category_id) VALUES (%s, %s, %s)",
                    (amount, description, category_id)
                )
                conn.commit()
            flash("Transação registada com sucesso!", "success")
            return redirect(url_for('main.transactions'))
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao registar transação: {e}", "error")

    # Capturar filtro por tipo (se houver)
    filtro_tipo = request.args.get('tipo', '')
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, type FROM categories WHERE user_id = %s ORDER BY name;", (user_id,))
            user_categories = cursor.fetchall()
            
            # Query dinâmica com filtro opcional
            query = """
                SELECT t.id, t.amount, t.description, t.transaction_at, c.name as category_name, c.type as category_type
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE c.user_id = %s
            """
            params = [user_id]
            
            if filtro_tipo in ['receita', 'despesa']:
                query += " AND c.type = %s"
                params.append(filtro_tipo)
                
            query += " ORDER BY t.transaction_at DESC;"
            
            cursor.execute(query, params)
            user_transactions = cursor.fetchall()
    except Exception as e:
        user_categories = []
        user_transactions = []
        flash(f"Erro ao carregar dados: {e}", "error")
    finally:
        db.put_connection(conn)
        
    return render_template('transactions.html', categories=user_categories, transactions=user_transactions, filtro_atual=filtro_tipo)