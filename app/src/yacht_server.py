import socket
import json
import threading
import random
import time


class YachtServer:
    def __init__(self):
        self.clients = []
        self.game_state = {
            "current_player": 0,
            "players": [
                {"name": "Player1", "scores": {}, "turn_data": {}},
                {"name": "Player2", "scores": {}, "turn_data": {}}
            ],
            "round": 1,
            "game_over": False
        }
        self.categories = [
            "ones", "twos", "threes", "fours", "fives", "sixes",
            "three_of_kind", "four_of_kind", "full_house",
            "small_straight", "large_straight", "yacht", "chance"
        ]

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('localhost', 8888))
        server.listen(2)
        self.log("서버 시작 - 포트 8888")

        while len(self.clients) < 2:
            client, addr = server.accept()
            self.clients.append(client)
            self.log(f"플레이어 {len(self.clients)} 접속: {addr}")
            threading.Thread(target=self.handle_client, args=(client, len(self.clients) - 1)).start()

        # 게임 시작 알림
        self.log("게임 시작!")
        self.broadcast({"type": "game_start", "data": self.game_state})

    def handle_client(self, client, player_id):
        # 클라이언트에게 플레이어 ID 전송
        welcome_msg = {"type": "player_id", "data": {"id": player_id}}
        client.send(json.dumps(welcome_msg).encode())
        self.log(f"플레이어 {player_id + 1}에게 ID 할당")

        while True:
            try:
                data = client.recv(1024).decode()
                if not data:
                    break

                message = json.loads(data)
                self.log(f"플레이어 {player_id + 1}에서 수신: {message['type']}")
                self.process_message(message, player_id)

            except Exception as e:
                self.log(f"클라이언트 {player_id + 1} 오류: {e}")
                break

        client.close()
        self.log(f"플레이어 {player_id + 1} 연결 종료")

    def process_message(self, message, player_id):
        if message["type"] == "roll_dice":
            if player_id == self.game_state["current_player"]:
                # 첫 굴리기 또는 재굴리기 처리
                current_turn = self.game_state["players"][player_id]["turn_data"]

                if "dice" not in current_turn:
                    # 첫 굴리기
                    dice = [random.randint(1, 6) for _ in range(5)]
                    current_turn["dice"] = dice
                    current_turn["rolls_left"] = 2
                    self.log(f"플레이어 {player_id + 1} 첫 굴리기: {dice}")
                else:
                    # 재굴리기
                    reroll_indices = message["data"].get("reroll", [])
                    dice = current_turn["dice"].copy()
                    old_dice = dice.copy()
                    for i in reroll_indices:
                        if 0 <= i < 5:
                            dice[i] = random.randint(1, 6)
                    current_turn["dice"] = dice
                    current_turn["rolls_left"] -= 1
                    self.log(f"플레이어 {player_id + 1} 재굴리기 {reroll_indices}: {old_dice} -> {dice}")

                self.broadcast({
                    "type": "dice_result",
                    "data": {
                        "dice": current_turn["dice"],
                        "player": player_id,
                        "rolls_left": current_turn["rolls_left"]
                    }
                })

        elif message["type"] == "select_category":
            if player_id == self.game_state["current_player"]:
                category = message["data"]["category"]
                dice = self.game_state["players"][player_id]["turn_data"]["dice"]
                score = self.calculate_score(dice, category)

                self.game_state["players"][player_id]["scores"][category] = score
                self.game_state["players"][player_id]["turn_data"] = {}

                self.log(f"플레이어 {player_id + 1} 점수 기록: {category} = {score}")

                # 턴 변경
                self.game_state["current_player"] = 1 - self.game_state["current_player"]

                # 게임 종료 체크
                if len(self.game_state["players"][player_id]["scores"]) == 13:
                    if len(self.game_state["players"][1 - player_id]["scores"]) == 13:
                        self.end_game()
                        return

                self.broadcast({
                    "type": "turn_end",
                    "data": {
                        "score": score,
                        "category": category,
                        "player": player_id,
                        "game_state": self.game_state
                    }
                })

    def calculate_score(self, dice, category):
        counts = [0] * 7
        for d in dice:
            counts[d] += 1

        if category in ["ones", "twos", "threes", "fours", "fives", "sixes"]:
            num = ["", "ones", "twos", "threes", "fours", "fives", "sixes"].index(category)
            return counts[num] * num

        elif category == "three_of_kind":
            return sum(dice) if max(counts) >= 3 else 0
        elif category == "four_of_kind":
            return sum(dice) if max(counts) >= 4 else 0
        elif category == "full_house":
            return 25 if (3 in counts and 2 in counts) else 0
        elif category == "small_straight":
            straights = [[1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6]]
            for straight in straights:
                if all(counts[i] > 0 for i in straight):
                    return 30
            return 0
        elif category == "large_straight":
            if (counts[1:6] == [1, 1, 1, 1, 1]) or (counts[2:7] == [1, 1, 1, 1, 1]):
                return 40
            return 0
        elif category == "yacht":
            return 50 if max(counts) == 5 else 0
        elif category == "chance":
            return sum(dice)

        return 0

    def end_game(self):
        scores = [sum(p["scores"].values()) for p in self.game_state["players"]]
        winner = 0 if scores[0] > scores[1] else 1

        self.broadcast({
            "type": "game_end",
            "data": {
                "winner": winner,
                "scores": scores
            }
        })

    def broadcast(self, message):
        data = json.dumps(message).encode()
        for client in self.clients:
            try:
                client.send(data)
            except:
                pass


if __name__ == "__main__":
    server = YachtServer()
    server.start_server()