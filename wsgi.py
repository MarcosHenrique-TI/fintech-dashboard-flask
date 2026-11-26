#importa a função Create_app dentro de Fintech
from fintech import create_app
#Chama a fábrica da aplicação e guarda a instância Flask retornada em app
app = create_app()
# Executa o servidor de desenvolvimento apenas se o arquivo for rodado diretamente
if __name__ == "__main__":
    # Escuta apenas localmente (127.0.0.1) na porta 5000 e recarrega ao salvar mudanças no código
    app.run(host="127.0.0.1", port=5000, debug=True)