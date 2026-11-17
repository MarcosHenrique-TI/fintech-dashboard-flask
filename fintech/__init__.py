import os
from flask import Flask
from fintech.db import db

def create_app():
    # Define o caminho correto para a pasta de templates na raiz
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    app = Flask(__name__, template_folder=template_dir)

    # Carrega as configurações
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "chave-padrao-insegura")
    app.config["DATABASE_URL"] = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/fintech")

    # Inicializa o banco de dados
    db.init_app(app)

    # Regista o encerramento da conexão com o banco após cada requisição
    app.teardown_appcontext(db.put_connection)

    # Regista o Blueprint com as rotas
    from fintech.routes import bp
    app.register_blueprint(bp)

    return app