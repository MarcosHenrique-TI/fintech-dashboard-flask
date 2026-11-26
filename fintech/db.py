import logging #registra mensagens de log
from flask import g #guarda dados que duram só durante aquela requisição
from psycopg2.extras import RealDictCursor #altera o cursor do psycopg2 para que cada linha retornada pelo SQL venha como um dicionário (linha['coluna']
from psycopg2.pool import ThreadedConnectionPool #mantém um grupo reaproveitável de conexões abertas com o PostgreSQL e gerencia o empréstimo (getconn) e devolução (putconn) de forma segura entre múltiplas threads/requisições


# Cria um logger nomeado com o caminho do módulo atual ('fintech.db') para registrar mensagens do arquivo
logger = logging.getLogger(__name__)

#criação da classe Database
class Database:
    #Construtor da instância Database; se receber um app Flask, já inicializa o pool de conexões
    def __init__(self, app=None):
        # Inicia o pool como None antes de configurar a aplicação
        self.pool = None
        # Se um app Flask foi passado no construtor, já monta o pool imediatamente
        if app is not None:
            self.init_app(app)

    # Configura e inicializa o pool de conexões do PostgreSQL a partir das configs do app Flask
    def init_app(self, app):
        # Lê a URL de conexão do banco configurada na aplicação
        database_url = app.config.get("DATABASE_URL")
        # Cria o pool de 1 a 10 conexões com timeout de 5s e cursores no formato dicionário
        self.pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=database_url,
            connect_timeout=5,
            cursor_factory=RealDictCursor,
        )
        # Registra no log da aplicação que o pool está pronto para uso
        app.logger.info("PostgreSQL connection pool initialized.")
    
    #Retorna uma conexão ativa para a requisição atual, pegando do pool apenas se necessário
    def get_connection(self):
        # Verifica se ainda não há conexão salva em 'g' ou se ela já está fechada
        if not hasattr(g, "db_conn") or g.db_conn.closed:
            try:
                #Solicita uma conexão ao pool e guarda em 'g' para reutilizar na requisição
                g.db_conn = self.pool.getconn()
            except Exception as exc:
                # Falhas de encoding no driver costumam mascarar credenciais inválidas ou lc_messages.
                logger.error("Failed to acquire PostgreSQL connection: %s", exc)
                # Lança erro de aplicação preservando a exceção original em __cause__
                raise RuntimeError("Não foi possível conectar ao banco de dados.") from exc
        return g.db_conn
    
    # Devolve a conexão da requisição atual para o pool e limpa a referência em 'g'
    def put_connection(self, exception=None):
        # Retira 'db_conn' de 'g' (retorna None se não houver conexão aberta na requisição)
        conn = g.pop("db_conn", None)
        if conn is not None and self.pool:
            #Se houve exceção na requisição, desfaz transação aberta antes de devolver ao pool
            if exception is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            # Retorna a conexão para reutilização no pool
            self.pool.putconn(conn)

# Instancia o gerenciador de banco sem inicializar o pool até chamar db.init_app(app)
db = Database()