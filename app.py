from flask import Flask, jsonify, Response
from flask_cors import CORS  # Импортируем Flask-CORS
from mcstatus import MinecraftServer
import requests

app = Flask(__name__)

# Включаем CORS для всего приложения
CORS(app, resources={r"/api/*": {"origins": ["https://egzotik.github.io", "https://egzotik.github.io/mixmonitoring/"]}})

SERVER_CONFIG = {
    "ip": "88.99.104.215",
    "port": 25566,
    "version": "1.5.2",
    "max_players": 100
}

def get_server_status():
    try:
        # Подключаемся к серверу
        server = MinecraftServer(SERVER_CONFIG['ip'], SERVER_CONFIG['port'])
        query = server.query()  # Пробуем запросить игроков

        return {
            "status": "online" if query else "offline",  # Проверяем, доступен ли сервер
            "version": SERVER_CONFIG["version"],  # Просто фиксированная версия
            "players": {
                "online": query.players.online if query else 0,
                "max": SERVER_CONFIG["max_players"],
                "list": query.players.names if query else []
            }
        }

    except Exception as e:
        print(f"Ошибка: {e}")  # Логируем ошибку для дебага
        return {
            "status": "offline",
            "version": None,
            "players": {
                "online": 0,
                "max": SERVER_CONFIG["max_players"],
                "list": []
            }
        }

@app.route('/api/status')
def api_status():
    return jsonify(get_server_status())

@app.route('/api/player_head/<string:player_name>')
def player_head(player_name):
    url = f"https://files.mix-servers.com/web/skins/{player_name}.png"
    r = requests.get(url)
    if r.status_code != 200:
        return Response(status=404)
    return Response(r.content, mimetype='image/png',
                    headers={"Cache-Control": "public, max-age=3600"})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
